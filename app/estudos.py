# Disparo automatico do estudo devocional apos cada gravacao.
#
# Quando uma sessao termina, o MP3 final entra numa fila e um trabalhador
# unico chama o pipeline externo (sermon-pipeline/pipeline.py), que faz
# NotebookLM -> estudo -> PDF -> WhatsApp. A chamada e serializada (uma
# gravacao de cada vez) e nunca bloqueia a interface.
#
# Tudo e opcional: sem "estudos.python"/"estudos.pasta" no config, ou com
# "estudos.ativo" desligado, nada acontece. O upload do audio para o Drive
# ja e feito pelo proprio gravador (OAuth), por isso o pipeline roda com
# --skip-drive; o numero do WhatsApp vem de "estudos.whatsapp" (vazio =
# numero padrao gravado no proprio pipeline).
#
# AUTENTICACAO DO NOTEBOOKLM (camada propria - nada a ver com o Drive):
# antes de cada disparo a sessao e verificada com
# "notebooklm auth check --test --passive" (somente leitura, nao renova
# nada). Sessao expirada rende UMA tentativa do caminho oficial
# ("auth refresh"); se a renovacao exigir login no navegador, o job nao
# morre - ele passa a AGUARDANDO_INTERVENCAO no banco com aviso
# (estudo_aguardando_auth) e o MP3, o upload do Drive e todos os passos
# concluidos ficam intactos. Assim que a sessao volta (login pelo painel
# ou checagem periodica), os jobs em espera voltam para PENDENTE e
# continuam DIRETO do NotebookLM, sem refazer gravacao nem upload. A
# checagem periodica e moderada e passiva: falha de rede nao invalida
# nada e nenhum refresh roda em loop.
#
# PERSISTENCIA (S2): a fila NAO e mais memoria - cada disparo e uma linha
# na tabela `jobs` do SQLite (estado/etapa/prova gravada). Job nao se perde
# em reinicio: `retomar_apos_reinicio()` devolve a fila o que estava em
# execucao, a nao ser que o log de handoff prove a conclusao. A fonte de
# verdade e o banco; a memoria guarda apenas o cache de saude da sessao.
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import config
from .db import db
from .logging_setup import get
from .notify import notify

log = get("estudos")

_evento = threading.Event()
_trabalhador: Optional[threading.Thread] = None

# saude da sessao do NotebookLM, cache em memoria: o painel le este bloco
# sem rodar nada; a verificacao de verdade acontece no disparo, no botao
# Diagnostico e no periodo de saude.
_trava_saude = threading.Lock()
_saude = {
    "estado": "desconhecido",
    "detalhe": "ainda nao verificado",
    "verificado_em": 0.0,
}
_ultima_renovacao = 0.0  # evita refresh em rajada quando vrios jobs em espera
_vigia: Optional[threading.Thread] = None
# sequencia de marcos do progresso (S3): sempre crescente, ver _seq()
_trava_seq = threading.Lock()
_ultima_seq = 0

_TTL_SAUDE = 600.0  # consulta sem "force" vale por 10 minutos
_RENOVAR_INTERVALO = 300.0  # no maximo uma renovacao a cada 5 minutos

# como distinguir "a rede falhou" de "a sessao morreu" na saida do CLI
_CHAVES_REDE = (
    "timed out",
    "timeout",
    "unreachable",
    "network",
    "connection",
    "getaddrinfo",
    "name or service",
    "temporary failure",
    "proxy",
    "certificate",
    "ssl",
    "tls",
    "dns",
)
_CHAVES_AUTH = (
    "expired",
    "not authenticated",
    "authentication",
    "signed out",
    "re-auth",
    "reauth",
    "unauthorized",
    "401",
    "credentials",
    "login",
    "cookie",
    "session",
)

_DETALHE = {
    "ok": "sessao valida",
    "auth": "sessao do NotebookLM expirada",
    "rede": "sem resposta do NotebookLM (rede)",
    "desconhecido": "nao foi possivel verificar a sessao",
}


def _cfg(chave: str) -> str:
    return str(config.get("estudos." + chave, "") or "").strip()


def ligado() -> bool:
    """True quando ha pipeline configurado e o recurso nao foi desligado."""
    ativo = config.get("estudos.ativo", True)
    return bool(ativo) and bool(_cfg("python")) and bool(_cfg("pasta"))


# ---------------------------------------------------------------------
# verificacao da sessao do NotebookLM
# ---------------------------------------------------------------------
def _nlm_programa(pasta: str) -> str:
    """Caminho do executavel do CLI.

    "estudos.notebooklm" no config tem prioridade (e e o que os testes e a
    maquina da igreja podem usar); o padrao e o proprio venv do
    sermon-pipeline, que e exatamente onde o "notebooklm login" interativo
    grava - mesmo perfil para o manual e o automatico.
    """
    explicito = _cfg("notebooklm")
    if explicito:
        return explicito
    base = Path(pasta) / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    nome = "notebooklm.exe" if os.name == "nt" else "notebooklm"
    return str(base / nome)


def _programa_existe(prog: str) -> bool:
    tem_caminho = ("/" in prog) or ("\\" in prog)
    if tem_caminho:
        return Path(prog).exists()
    return shutil.which(prog) is not None


def _executar_nlm(args, cwd: Path, timeout: int):
    """Roda o CLI sem janela. Devolve (codigo, texto); codigo None quando
    nem deu para executar (programa ausente) ou quando estourou o tempo."""
    comando = list(args)
    if comando and comando[0].lower().endswith((".bat", ".cmd")):
        comando = ["cmd", "/c"] + comando
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        proc = subprocess.run(
            comando,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError as exc:
        return None, str(exc)


def _classificar(codigo: Optional[int], texto: str) -> str:
    """ok | auth | rede | desconhecido a partir da saida do auth check."""
    if codigo == 0:
        return "ok"
    if codigo is None:
        # sem programa ou tempo estourado: nada conclusivo sobre a sessao
        return "rede" if "timeout" in (texto or "").lower() else "desconhecido"
    baixo = (texto or "").lower()
    if any(chave in baixo for chave in _CHAVES_REDE):
        return "rede"
    if any(chave in baixo for chave in _CHAVES_AUTH):
        return "auth"
    # falhou sem cara de rede nem de sessao: nao bloqueia o disparo e o
    # proprio pipeline segue cuidando do erro (comportamento antigo)
    return "desconhecido"


def _definir(estado: str, detalhe: str) -> str:
    with _trava_saude:
        _saude["estado"] = estado
        _saude["detalhe"] = detalhe
        _saude["verificado_em"] = time.time()
    return estado


def verificar_saude(force: bool = False) -> str:
    """Checa a sessao; devolve ok | auth | rede | desconhecido.

    Sem "force" usa o resultado recente (custo zero para quem consulta
    a tela). O comando e somente leitura: nunca renova credencial sozinho.
    """
    pasta = _cfg("pasta")
    if not pasta:
        return "desconhecido"
    agora = time.time()
    with _trava_saude:
        if not force and agora - _saude["verificado_em"] < _TTL_SAUDE:
            return str(_saude["estado"])

    prog = _nlm_programa(pasta)
    if not _programa_existe(prog):
        return _definir("desconhecido", "notebooklm nao encontrado")

    codigo, texto = _executar_nlm(
        [prog, "auth", "check", "--test", "--passive"], Path(pasta), 60
    )
    estado = _classificar(codigo, texto)
    if texto and estado != "ok":
        log.warning("auth check (%s): %s", estado, texto.strip()[:400])
    else:
        log.info("auth check: %s", estado)
    return _definir(estado, _DETALHE[estado])


def _renovar_sessao() -> bool:
    """Uma tentativa UNICA de recuperacao, pelos metodos oficiais da
    biblioteca, nesta ordem:

    1. "auth refresh --browser-cookies" - re-extrai os cookies da sessao
       ja logada no navegador instalado (o login foi feito UMA vez pelo
       usuario; aqui so lemos o resultado) e regrava o storage;
    2. "auth refresh --allow-headless" - recuperacao layer-3 pela sessao
       persistida do proprio CLI.

    Se as duas exigirem login interativo, devolve False e o job vai para
    a espera - nada de segurar cookie na mao nem de tentar para sempre.
    """
    global _ultima_renovacao
    pasta = _cfg("pasta")
    prog = _nlm_programa(pasta)
    if not pasta or not _programa_existe(prog):
        return False
    agora = time.time()
    if agora - _ultima_renovacao < _RENOVAR_INTERVALO:
        log.info("renovacao pulada: ja tentada ha pouco")
        return False
    _ultima_renovacao = agora

    navegador = (_cfg("browser") or "msedge").lower()
    navegador = "edge" if navegador in ("msedge", "edge") else navegador
    tentativas = [
        [prog, "auth", "refresh", "--browser-cookies", navegador, "--verify"],
        [prog, "auth", "refresh", "--allow-headless", "--verify"],
    ]
    for args in tentativas:
        codigo, texto = _executar_nlm(args, Path(pasta), 300)
        log.info("auth refresh %s: codigo %s", args[3], codigo)
        if texto.strip():
            log.info("auth refresh saida: %s", texto.strip()[:400])
        if codigo == 0:
            return True
    return False


# ---------------------------------------------------------------------
# lista de espera (preservacao do job) e retomada
# ---------------------------------------------------------------------
def _aguardar(job_id: str, motivo: str) -> None:
    if not db.job_aguardar(job_id, motivo):
        return  # ja tinha saido de EXECUTANDO (corrida): nada a guardar
    log.warning("job %s em espera (%s)", job_id, motivo)
    if motivo == "autenticacao expirada":
        notify(
            "estudo_aguardando_auth",
            "Autenticacao do NotebookLM expirada - estudo pausado, nada "
            "se perdeu. Renove o login pelo painel (Config > Estudo) ou "
            "mantenha a sessao Google do navegador ativa; ele retoma "
            "sozinho.",
            level="warning",
        )
    else:
        notify(
            "estudo_aguardando_rede",
            "Sem conexao com o NotebookLM - estudo pausado, nada se "
            "perdeu; sera retomado automaticamente quando a rede voltar.",
            level="warning",
        )


def _retomar_pendentes() -> int:
    """Devolve os jobs em espera para a fila. So chamar quando a sessao
    foi CONFIRMADA valida (evita oscilar entre espera e disparo)."""
    novos = db.job_retomar()
    if not novos:
        return 0
    log.info("%d estudo(s) em espera retomado(s)", novos)
    notify(
        "estudo_retomando",
        f"Sessao do NotebookLM OK - {novos} estudo(s) em espera "
        f"retomado(s)",
        level="info",
    )
    _evento.set()
    return novos


# ---------------------------------------------------------------------
# API para o painel (indicadores, diagnostico e renovacao do login)
# ---------------------------------------------------------------------
def status() -> Dict[str, Any]:
    """Leitura barata do estado - o painel e o MQTT podem consultar a
    qualquer momento sem tocar na rede."""
    with _trava_saude:
        saude = dict(_saude)
    contagens = db.job_contagens()
    pendentes = contagens.get("AGUARDANDO_INTERVENCAO", 0)
    fila = contagens.get("PENDENTE", 0)
    motivo = db.job_motivo() if pendentes else ""
    if not ligado():
        return {
            "ativo": False,
            "estado": "desconhecido",
            "detalhe": "estudo nao configurado neste equipamento",
            "verificado_em": saude.get("verificado_em", 0.0),
            "aguardando": 0,
            "motivo": "",
            "fila": fila,
            # a barra da cadeia nao depende do recurso estar ligado: o
            # estado da ULTIMA gravacao/estudo continua sendo a verdade
            "job": _job_publico(),
            "barra": barra(),
        }
    return {
        "ativo": True,
        "estado": saude.get("estado", "desconhecido"),
        "detalhe": saude.get("detalhe", ""),
        "verificado_em": saude.get("verificado_em", 0.0),
        "aguardando": pendentes,
        "motivo": motivo,
        "fila": fila,
        "job": _job_publico(),
        "barra": barra(),
    }


def diagnosticar() -> Dict[str, Any]:
    """Botao DIAGNOSTICAR: verificacao fresca +, se a sessao estiver
    expirada, UMA renovacao oficial na hora. Retoma o que estiver em
    espera quando a sessao voltar."""
    if not ligado():
        return status()
    estado = verificar_saude(force=True)
    renovada = False
    if estado == "auth":
        log.info("diagnostico: tentando renovar a sessao")
        if _renovar_sessao():
            _definir("ok", "sessao renovada automaticamente")
            estado = "ok"
            renovada = True
    retomados = _retomar_pendentes() if estado == "ok" else 0
    # tambem acorda o trabalhador para PENDENTE puro (ex.: job criado
    # fora do fluxo normal ou congelado com o estudo desligado): o
    # pre-flight dentro dele decide se roda ou guarda
    if db.job_contagens().get("PENDENTE"):
        _iniciar()
        _evento.set()
    resultado = status()
    resultado["renovada"] = renovada
    resultado["retomados"] = retomados
    return resultado


def reconectar() -> Dict[str, Any]:
    """Botao RENOVAR LOGIN: abre o login do NotebookLM em janela propria
    (o login acontece uma unica vez, no navegador).

    A saida do comando vai para um arquivo de log: a janela de console
    pode fechar sozinha quando o comando termina rapido, e sem o arquivo
    uma falha (por exemplo, Edge de perfil travado em uso) fica
    diagnosticavel apenas pelo terminal.
    """
    if not ligado():
        raise ValueError("estudo automatico nao configurado neste equipamento")
    pasta = _cfg("pasta")
    prog = _nlm_programa(pasta)
    if not _programa_existe(prog):
        raise ValueError("notebooklm nao encontrado - confira estudos.pasta")
    navegador = _cfg("browser") or "msedge"
    comando = [prog, "login", "--browser", navegador]
    if prog.lower().endswith((".bat", ".cmd")):
        comando = ["cmd", "/c"] + comando
    logs = Path(pasta) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    arquivo = logs / "login_nlm.log"
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    with open(arquivo, "a", encoding="utf-8") as fh:
        fh.write(
            f"# login {datetime.now().isoformat(timespec='seconds')} "
            f"(browser={navegador})\n"
        )
        fh.flush()
        subprocess.Popen(
            comando,
            cwd=pasta,
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
    # rotacao: cada login abre o arquivo em append; sem teto ele cresce
    # para sempre
    if arquivo.stat().st_size > 2 * 1024 * 1024:
        anterior = logs / "login_nlm.log.1"
        if anterior.exists():
            anterior.unlink()
        arquivo.replace(anterior)
    log.info(
        "janela de login do NotebookLM aberta (browser=%s, log=%s)",
        navegador,
        arquivo.name,
    )
    return {"lancado": True, "navegador": navegador}


def _keepalive() -> None:
    """Renovacao oficial de cadencia, exatamente como a propria
    biblioteca documenta para uso desassistido (scheduler de sistema,
    cadencia recomendada de 15-20 minutos): rotaciona os cookies ENQUANTO
    eles ainda sao validos e confirma com --verify.

    Guardas importantes: so roda quando a verificacao acabou de dizer que
    a sessao esta VIVA (sessao morta = chamada inutil, nao vira loop de
    tentativas) e respeita o mesmo intervalo minimo de qualquer outra
    renovacao. Falha aqui e apenas registrada - quem decide retomar e a
    verificacao de saude.
    """
    global _ultima_renovacao
    pasta = _cfg("pasta")
    prog = _nlm_programa(pasta)
    if not pasta or not _programa_existe(prog):
        return
    agora = time.time()
    if agora - _ultima_renovacao < _RENOVAR_INTERVALO:
        return
    _ultima_renovacao = agora
    codigo, texto = _executar_nlm(
        [prog, "auth", "refresh", "--verify"], Path(pasta), 120
    )
    log.info("keepalive (auth refresh --verify): codigo %s", codigo)
    if codigo != 0 and texto.strip():
        log.warning("keepalive saida: %s", texto.strip()[:300])


def _limpar_logs_antigos(manter: int = 30, teto_mb: float = 2.0) -> None:
    """Rotina de housekeeping dos logs do estudo.

    handoff_<selo>.log nasce um por execucao: sem teto, meses de culto
    viram centenas de arquivos esquecidos. login_nlm.log e aberto em
    append por cada janela de login: rotaciona ao passar do teto.
    """
    logs = Path(_cfg("pasta")) / "logs"
    try:
        handoffs = sorted(logs.glob("handoff_*.log"))
        for antigo in handoffs[:-manter]:
            antigo.unlink()
        login = logs / "login_nlm.log"
        if login.exists() and login.stat().st_size > teto_mb * 1024 * 1024:
            for indice in (2, 3):
                velho = logs / f"login_nlm.log.{indice}"
                if velho.exists():
                    velho.unlink()
            anterior = logs / "login_nlm.log.1"
            if anterior.exists():
                anterior.unlink()
            login.replace(anterior)
    except OSError as exc:
        log.debug("limpeza de logs ignorada: %s", exc)


def retomar_apos_reinicio() -> int:
    """Recuperacao no boot (chamada por `iniciar()` na subida do painel).

    O que estava EXECUTANDO quando o processo morreu volta para a fila -
    a nao ser que o log de handoff prove a conclusao (marcador
    '=== CONCLUIDO', impresso somente depois que o pipeline terminou o
    envio). A prova vem do arquivo gravado, nunca de memoria; jobs em
    outros estados nao sao tocados. Devolve quantos voltaram a fila.
    """
    total = 0
    for job in db.jobs_em_execucao():
        resultado = job.get("resultado") or ""
        provado = False
        if resultado:
            try:
                texto = Path(resultado).read_text(
                    encoding="utf-8", errors="replace"
                )
                provado = "=== CONCLUIDO" in texto
            except OSError:
                provado = False
        if provado:
            # a prova vale para os DOIS marcos finais: "=== 8. Enviando"
            # = envio em curso confirmado; "pulado" = o pipeline acabou
            # sem numero para enviar - la fora a barra nunca marca 100%
            # sem WhatsApp real
            enviado = "=== 8. Enviando" in texto
            pulado = "por WhatsApp pulado" in texto
            etapa_final = "FINAL" if enviado and not pulado else "FINAL_SEM_ENVIO"
            db.job_concluir(
                job["job_id"], resultado=resultado, etapa=etapa_final
            )
            log.info(
                "job de %s ja estava concluido (log de handoff) - "
                "marcado CONCLUIDO",
                Path(job["audio_path"]).name,
            )
        else:
            db.job_reenfileirar(job["job_id"])
            log.warning(
                "job de %s interrompido pelo reinicio - devolvido a fila",
                Path(job["audio_path"]).name,
            )
            total += 1
    if total:
        notify(
            "estudos_retomando",
            f"{total} estudo(s) interrompidos pelo reinicio devolvidos "
            f"a fila",
            level="warning",
        )
        _iniciar()
        _evento.set()
    return total


def iniciar() -> None:
    """Periodo de saude da sessao (chamado na subida do painel).

    Moderado de proposito: um passeio a cada 20 minutos (cadencia
    recomendada pelo proprio CLI para uso desassistido). A verificacao e
    somente leitura; falha de rede nao invalida nada (o ultimo estado
    conhecido permanece); com a sessao confirmada valida roda o
    keepalive oficial e retoma o que estiver em espera. Com a sessao
    morta, o vigia NAO tenta renovar em loop - renovacao acontece no
    disparo (uma vez) ou no botao.

    Antes de tudo, a recuperacao pos-reinicio dos jobs interrompidos
    (idempotente: so toca em EXECUTANDO).
    """
    global _vigia
    retomar_apos_reinicio()
    if _vigia is not None and _vigia.is_alive():
        return
    _vigia = threading.Thread(target=_vigia_loop, name="estudos-saude", daemon=True)
    _vigia.start()


def _vigia_loop() -> None:
    while True:
        try:
            intervalo = float(config.get("estudos.saude_intervalo", 1200) or 1200)
        except (TypeError, ValueError):
            intervalo = 1200.0
        time.sleep(max(60.0, intervalo))
        try:
            if not ligado():
                continue
            estado = verificar_saude(force=True)
            if estado == "ok":
                _keepalive()
                _retomar_pendentes()
            # a casa nao se limpa sozinha: logs do estudo tambem rodam
            # aqui dentro do mesmo passeio periodico
            _limpar_logs_antigos()
            # auto-curacao: um PENDENTE sem dono acordando (banco tocado
            # fora do fluxo, estudo religado) nao espera ate a proxima
            # gravacao para andar
            if db.job_contagens().get("PENDENTE"):
                _iniciar()
                _evento.set()
            # auth: so atualiza o indicador; a renovacao acontece no
            # disparo ou no botao, nunca em loop
        except Exception:  # noqa: BLE001 - o vigia nunca morre
            log.exception("falha no periodo de saude do NotebookLM")


# ---------------------------------------------------------------------
# progresso por job (S3): marcos REAIS da cadeia
# GRAVACAO -> MP3 -> DRIVE -> NOTEBOOKLM -> ESTUDO -> PDF -> WHATSAPP
# ---------------------------------------------------------------------
# Quantos marcos da cadeia o pipeline ja deixou para tras em cada etapa.
# Marca-se somente o que foi CONCLUIDO e com prova: os marcos 1-3 vem da
# gravacao no banco (ended_at, final_bytes, drive_file_id) e os marcos
# 4-7 das linhas "=== N." que o proprio pipeline imprime (flush por
# passo) no log de handoff. 100% exige WhatsApp confirmado (codigo 0 do
# pipeline com o passo 8 executado - nunca estimativa de tempo).
_MARCOS_PIPELINE = {
    "PRE-FLIGHT": 0,
    "NOTEBOOKLM": 0,
    "ESTUDO": 1,  # "=== 5." visto: fonte pronta, estudo em geracao
    "PDF": 2,  # "=== 6." visto: relatorio baixado
    "WHATSAPP": 3,  # "=== 8." visto: pdf pronto, envio em curso
    "FINAL": 4,  # WhatsApp confirmado
    "FINAL_SEM_ENVIO": 3,  # concluiu sem enviar (numero nao configurado)
}

_DESCRICOES = {
    "PRE-FLIGHT": "Verificando a sessao do NotebookLM",
    "NOTEBOOKLM": "NotebookLM preparando o audio",
    "ESTUDO": "Gerando o estudo devocional",
    "PDF": "Convertendo o estudo em PDF",
    "WHATSAPP": "Enviando o PDF por WhatsApp",
    "FINAL": "Enviado por WhatsApp",
    "FINAL_SEM_ENVIO": "Estudo pronto (WhatsApp nao configurado - envio pulado)",
}


def _sessao_do_job(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rec = job.get("recording_id")
    if not rec:
        return None
    try:
        return db.get_session(rec)
    except Exception:  # noqa: BLE001 - barra nunca derruba o painel
        return None


def _marcos_concluidos(job: Dict[str, Any], etapa: Optional[str] = None) -> int:
    """0..7: quantos marcos da cadeia tem PROVA gravada."""
    etapa = etapa or str(job.get("etapa") or "PRE-FLIGHT")
    base = 0
    sess = _sessao_do_job(job)
    if sess and sess.get("ended_at"):
        base += 1
    if sess and (sess.get("final_bytes") or 0) > 0:
        base += 1
    if job.get("drive_file_id") or (sess and sess.get("drive_file_id")):
        base += 1
    return base + _MARCOS_PIPELINE.get(etapa, 0)


def _percentual(marcos: int) -> int:
    return round(100 * max(0, min(7, marcos)) / 7)


def _seq() -> int:
    """Sequencia de progresso sempre crescente.

    Base epoch-ms, mas empurrada para o proximo inteiro quando duas
    emissoes caem no MESMO milissegundo (ex.: drenagem final vendo o
    passo 8 e o proprio job concluindo): o agente descarta ``seq <=
    ultima``, entao empate faria o marco final sumir do celular.
    """
    global _ultima_seq
    with _trava_seq:
        candidato = int(time.time() * 1000)
        _ultima_seq = max(candidato, _ultima_seq + 1)
        return _ultima_seq


def _publicar_job(
    job: Dict[str, Any],
    etapa: str,
    *,
    descricao: Optional[str] = None,
    estado: Optional[str] = None,
    level: str = "info",
) -> None:
    """Marco real do job: notifica o painel (SSE) e o celular (o agente
    republica no topic MQTT retido).

    O payload carrega ``seq`` monotona: o agente descarta sequencia
    antiga, entao uma mensagem velha na fila de reconexao nunca faz a
    barra voltar para uma etapa que ja passou.
    """
    etapa = etapa or str(job.get("etapa") or "PRE-FLIGHT")
    payload = {
        "job_id": job.get("job_id"),
        "recording_id": job.get("recording_id"),
        "estado": estado or str(job.get("estado") or ""),
        "etapa": etapa,
        "percentual": _percentual(_marcos_concluidos(job, etapa)),
        "descricao": descricao or _DESCRICOES.get(etapa, etapa),
        "motivo": str(job.get("motivo") or ""),
        "seq": _seq(),
        "ts": time.time(),
    }
    notify("job_progress", payload["descricao"], level=level, payload=payload)


def _drenar_log(
    caminho: Path, pos: int, job: Dict[str, Any], visto: Dict[str, bool]
) -> int:
    """Le o que surgiu no log de handoff desde ``pos`` e emite os marcos.

    As linhas "=== N." sao gravadas com flush pelo proprio pipeline a
    cada passo concluido - entao ve-las no arquivo e prova de que a
    etapa terminou (nada de estimar por tempo). Devolve a nova posicao
    consumida: a linha incompleta do fim e re-lida na proxima drenagem,
    nunca processada duas vezes.
    """
    try:
        with open(caminho, "rb") as fh:
            fh.seek(pos)
            novos = fh.read()
    except OSError:
        return pos
    if b"\n" not in novos:
        return pos
    completo, _resto = novos.rsplit(b"\n", 1)
    atual = job
    for bruta in completo.split(b"\n"):
        linha = bruta.decode("utf-8", errors="replace").strip()
        etapa = None
        if linha.startswith("=== 5."):
            etapa = "ESTUDO"
        elif linha.startswith("=== 6."):
            etapa = "PDF"
        elif linha.startswith("=== 8. Enviando"):
            etapa = "WHATSAPP"
            visto["envio"] = True
        elif linha.startswith("=== 8. Envio por WhatsApp pulado"):
            visto["pulado"] = True
        if etapa:
            db.update_job(atual["job_id"], etapa=etapa)
            atual = dict(atual, etapa=etapa)
            _publicar_job(atual, etapa)
    return pos + len(completo) + 1


def _job_publico() -> Optional[Dict[str, Any]]:
    """Ultimo job em linguagem de interface (sem caminhos internos)."""
    jobs = db.list_jobs(1)
    if not jobs:
        return None
    j = jobs[0]
    etapa = str(j.get("etapa") or "")
    return {
        "job_id": j.get("job_id"),
        "recording_id": j.get("recording_id"),
        "estado": j.get("estado"),
        "etapa": etapa,
        "percentual": _percentual(_marcos_concluidos(j)),
        "descricao": _DESCRICOES.get(etapa, ""),
        "motivo": j.get("motivo") or "",
        "erro": j.get("erro") or "",
        "tentativas": j.get("tentativas"),
        "created_at": j.get("created_at"),
        "updated_at": j.get("updated_at"),
        "finished_at": j.get("finished_at"),
    }


def barra() -> Dict[str, Any]:
    """Estado da cadeia GRAVACAO -> MP3 -> DRIVE -> NOTEBOOKLM -> ESTUDO
    -> PDF -> WHATSAPP para o painel e para o celular (S3).

    Cada passo so aparece concluido com prova no banco; percentual
    avanca somente por marco concluido; 100% exige WhatsApp confirmado.
    Passo ativo herda o tom do job: azul em execucao, amarelo em espera
    (sessao/rede), vermelho em erro. Sem nada a mostrar, "mostrar" e
    False e a interface esconde a barra.
    """
    job = None
    sess = None
    try:
        jobs = db.list_jobs(1)
        job = jobs[0] if jobs else None
        if job:
            sess = _sessao_do_job(job)
        else:
            sessoes = db.list_sessions(1)
            sess = sessoes[0] if sessoes else None
    except Exception:  # noqa: BLE001 - barra nunca derruba o painel
        log.exception("falha ao montar a barra de progresso")
    if not job and not sess:
        return {"mostrar": False, "percentual": 0, "etapas": []}

    etapas = []

    def _add(nome, concluido, ativo=False, tom=None):
        if tom is None:
            tom = "concluido" if concluido else ("ativo" if ativo else "pendente")
        etapas.append({"n": len(etapas) + 1, "nome": nome, "tom": tom})

    gravando = bool(sess and not sess.get("ended_at"))
    _add("GRAVACAO", bool(sess and sess.get("ended_at")), ativo=gravando)
    mp3_ok = bool(sess and (sess.get("final_bytes") or 0) > 0)
    _add("MP3", mp3_ok, ativo=bool(sess and sess.get("ended_at") and not mp3_ok))
    drive_ok = bool(
        (job and job.get("drive_file_id"))
        or (sess and sess.get("drive_file_id"))
    )
    _add("DRIVE", drive_ok, ativo=bool(sess and mp3_ok and not drive_ok))

    etapa_job = str((job or {}).get("etapa") or "")
    estado_job = str((job or {}).get("estado") or "")
    concluidos_pipeline = _MARCOS_PIPELINE.get(etapa_job, 0)
    tom_ativo = {
        "EXECUTANDO": "ativo",
        "AGUARDANDO_INTERVENCAO": "aguardando",
        "ERRO": "erro",
    }.get(estado_job)
    for nome, idx in (("NOTEBOOKLM", 0), ("ESTUDO", 1), ("PDF", 2), ("WHATSAPP", 3)):
        concluido = concluidos_pipeline > idx
        ativo = bool(job) and concluidos_pipeline == idx and tom_ativo is not None
        _add(nome, concluido, ativo=ativo, tom=tom_ativo if ativo else None)

    if estado_job == "ERRO":
        descricao = "Erro no estudo: " + str(
            (job or {}).get("erro") or "veja o painel"
        )[:120]
    elif estado_job == "AGUARDANDO_INTERVENCAO":
        descricao = "Estudo em espera: " + str((job or {}).get("motivo") or "sessao")
    elif estado_job == "PENDENTE":
        descricao = "Estudo na fila"
    elif job:
        descricao = _DESCRICOES.get(etapa_job, "Estudo em andamento")
    elif gravando:
        descricao = "Gravando"
    elif sess and not mp3_ok:
        descricao = "Convertendo para MP3"
    elif sess and not drive_ok:
        descricao = "Enviando ao Drive"
    else:
        descricao = "Concluido"

    marcos = _marcos_concluidos(job) if job else sum(
        1 for e in etapas if e["tom"] == "concluido"
    )
    return {
        "mostrar": True,
        "percentual": _percentual(marcos),
        "descricao": descricao,
        "estado": estado_job or ("RECORDING" if gravando else "COMPLETED"),
        "job_id": (job or {}).get("job_id"),
        "recording_id": (job or {}).get("recording_id")
        if job
        else (sess or {}).get("id"),
        "etapas": etapas,
        "ts": time.time(),
    }


# ---------------------------------------------------------------------
# fila e trabalhador
# ---------------------------------------------------------------------
def enfileirar(caminho: str) -> None:
    """Recebe o arquivo final de uma gravacao concluida."""
    if not config.get("estudos.ativo", True):
        log.info(
            "estudo automatico desligado - %s ignorado", Path(caminho).name
        )
        return
    if not _cfg("python") or not _cfg("pasta"):
        # recurso nao configurado neste equipamento: silencio absoluto
        return
    if not db.create_job(audio_path=caminho):
        # ja existe job para este audio (gravacao repetida = 1 job)
        return
    _iniciar()
    _evento.set()


def _iniciar() -> None:
    global _trabalhador
    if _trabalhador is not None and _trabalhador.is_alive():
        return
    _trabalhador = threading.Thread(target=_loop, name="estudos", daemon=True)
    _trabalhador.start()


def _loop() -> None:
    # ordem importa: sinal limpo ANTES de drenar a fila - enqueue posterior
    # reacende o sinal e enqueue durante a drenagem e visto na mesma passada
    while True:
        _evento.wait()
        _evento.clear()
        while ligado():
            job = db.claim_job()
            if job is None:
                break
            try:
                _rodar(job)
            except Exception as exc:  # noqa: BLE001 - o trabalhador nunca morre
                # a guarda do banco evita sobrescrever um CONCLUIDO que ja
                # tenha acontecido antes da excecao
                db.job_falhar(job["job_id"], str(exc))
                log.error(
                    "falha ao disparar estudo para %s: %s", job["audio_path"], exc
                )
                notify(
                    "estudo_erro",
                    f"Falha ao disparar o estudo: {exc}",
                    level="error",
                )


def _publica_falha(job_id: str, job: Dict[str, Any], descricao: str) -> None:
    """Marco vermelho de erro: estado/etapa verdadeiros vem do banco (a
    transicao ja aconteceu), nunca da copia antiga na memoria."""
    try:
        atual = db.get_job(job_id) or job
    except Exception:  # noqa: BLE001 - notificacao nunca derruba o job
        atual = job
    _publicar_job(
        atual,
        str(atual.get("etapa") or "PRE-FLIGHT"),
        descricao=descricao,
        estado="ERRO",
        level="error",
    )


def _rodar(job: Dict[str, Any]) -> None:
    job_id = job["job_id"]
    caminho = job["audio_path"]
    python = _cfg("python")
    pasta = _cfg("pasta")
    if not python or not pasta:
        db.job_falhar(job_id, "estudo desconfigurado no meio da fila")
        _publica_falha(job_id, job, "Estudo desconfigurado no meio da fila")
        return
    alvo = Path(pasta)
    if not (alvo / "pipeline.py").exists():
        log.warning("pipeline.py nao encontrado em %s - estudo nao disparado", alvo)
        db.job_falhar(job_id, f"pipeline.py nao encontrado em {alvo}")
        _publica_falha(
            job_id, job, "Pipeline do estudo nao encontrado (sermon-pipeline)"
        )
        notify(
            "estudo_erro",
            "Pipeline do estudo nao encontrado (sermon-pipeline)",
            level="error",
        )
        return

    # marco de entrada: gravacao+mp3+drive entram no payload ja provados
    # no banco; daqui em diante o percentual so avanca com marco real
    _publicar_job(job, "PRE-FLIGHT")

    # ---- pre-flight da sessao: preserva o job em vez de quebrar ------
    estado = verificar_saude(force=True)
    if estado == "auth":
        log.warning("sessao do NotebookLM expirada - uma tentativa de renovacao")
        if _renovar_sessao():
            _definir("ok", "sessao renovada automaticamente")
            estado = "ok"
    if estado == "auth":
        _aguardar(job_id, "autenticacao expirada")
        _publicar_job(
            dict(job, estado="AGUARDANDO_INTERVENCAO", motivo="autenticacao expirada"),
            "PRE-FLIGHT",
            descricao="Em espera: autenticacao do NotebookLM expirada",
            estado="AGUARDANDO_INTERVENCAO",
            level="warning",
        )
        return
    if estado == "rede":
        # sem conexao o pipeline tambem quebraria: guarda o MP3 e o
        # periodo de saude devolve o job quando a rede voltar
        _aguardar(job_id, "sem rede")
        _publicar_job(
            dict(job, estado="AGUARDANDO_INTERVENCAO", motivo="sem rede"),
            "PRE-FLIGHT",
            descricao="Em espera: sem rede",
            estado="AGUARDANDO_INTERVENCAO",
            level="warning",
        )
        return
    if estado == "ok":
        # sessao confirmada agora: aproveita para retomar o que ficou
        # em espera por uma falha anterior (roda depois deste job)
        _retomar_pendentes()

    cmd = [python, "pipeline.py", caminho, "--skip-drive"]
    numero = _cfg("whatsapp")
    if numero:
        cmd += ["--to", numero]

    logs = alvo / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    selo = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_log = logs / f"handoff_{selo}.log"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    log.info("disparando estudo: %s", " ".join(cmd))
    notify(
        "estudo_iniciando",
        f"Gerando estudo de {Path(caminho).name} (NotebookLM)...",
        level="info",
    )
    # prova gravada ANTES do disparo: se o processo morrer no meio, o
    # boot sabe o que rodava e onde olhar (etapa/resultado persistidos).
    # NOTEBOOKLM = etapa 4 da cadeia (os passos 3/4 do pipeline)
    db.update_job(job_id, etapa="NOTEBOOKLM", resultado=str(arquivo_log))
    job = dict(job, etapa="NOTEBOOKLM", resultado=str(arquivo_log))
    _publicar_job(job, "NOTEBOOKLM")
    visto = {"envio": False, "pulado": False}
    pos_log = 0
    with open(arquivo_log, "w", encoding="utf-8") as fh:
        fh.write(f"# handoff {selo}\n# cmd: {' '.join(cmd)}\n\n")
        fh.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(alvo),
            stdout=fh,
            stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        # drena o log a cada fracao de segundo emitindo somente marcos
        # que JA apareceram no arquivo (o pipeline grava cada passo com
        # flush): percentual nunca e estimado por tempo decorrido
        while True:
            pos_log = _drenar_log(arquivo_log, pos_log, job, visto)
            if proc.poll() is not None:
                break
            time.sleep(0.4)
        _drenar_log(arquivo_log, pos_log, job, visto)
        codigo = proc.wait()

    if codigo == 0:
        # 100% so com WhatsApp confirmado: o passo 8 ("Enviando PDF")
        # foi visto no log. Sem numero configurado o pipeline pula o
        # envio e o job conclui honestamente em 6/7 - nunca finge envio
        enviado = bool(visto["envio"]) and not bool(visto["pulado"])
        etapa_final = "FINAL" if enviado else "FINAL_SEM_ENVIO"
        db.job_concluir(job_id, resultado=str(arquivo_log), etapa=etapa_final)
        _publicar_job(
            dict(job, etapa=etapa_final, estado="CONCLUIDO"),
            etapa_final,
            descricao=None
            if enviado
            else "Estudo pronto (WhatsApp nao configurado - envio pulado)",
            estado="CONCLUIDO",
            level="success" if enviado else "warning",
        )
        log.info("estudo concluido (%s)", arquivo_log.name)
        notify(
            "estudo_pronto",
            "Estudo gerado e enviado por WhatsApp"
            if enviado
            else "Estudo gerado (WhatsApp nao configurado - envio pulado)",
            level="success",
        )
    else:
        db.job_falhar(
            job_id,
            f"pipeline terminou com codigo {codigo} - veja {arquivo_log.name}",
        )
        _publica_falha(
            job_id,
            job,
            f"Pipeline terminou com erro (codigo {codigo}) - veja {arquivo_log.name}",
        )
        log.error("pipeline terminou com codigo %s (%s)", codigo, arquivo_log)
        notify(
            "estudo_erro",
            f"Pipeline do estudo terminou com erro (codigo {codigo}) - "
            f"veja {arquivo_log.name}",
            level="error",
        )
