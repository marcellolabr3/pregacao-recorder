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
# morre - ele entra na lista de espera com aviso (estudo_aguardando_auth)
# e o MP3, o upload do Drive e todos os passos concluidos ficam intactos.
# Assim que a sessao volta (login pelo painel ou checagem periodica), os
# jobs em espera voltam para a fila e continuam DIRETO do NotebookLM, sem
# refazer gravacao nem upload. A checagem periodica e moderada e passiva:
# falha de rede nao invalida nada e nenhum refresh roda em loop.
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import config
from .logging_setup import get
from .notify import notify

log = get("estudos")

_fila: deque = deque()
_trava_fila = threading.Lock()
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
_aguardando: list = []  # jobs preservados aguardando sessao ou rede
_motivo = ""  # motivo da espera (aparece no "detail" do estado MQTT)
_ultima_renovacao = 0.0  # evita refresh em rajada quando vrios jobs em espera
_vigia: Optional[threading.Thread] = None

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
def _aguardar(caminho: str, motivo: str) -> None:
    global _motivo
    with _trava_fila:
        if caminho in _aguardando:
            return
        _aguardando.append(caminho)
        _motivo = motivo
    log.warning("estudo em espera (%s): %s", motivo, caminho)
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
    global _motivo
    with _trava_fila:
        if not _aguardando:
            return 0
        pendentes = list(_aguardando)
        _aguardando.clear()
        _motivo = ""
        novos = [p for p in pendentes if p not in _fila]
        _fila.extend(novos)
    if not novos:
        return 0
    log.info("%d estudo(s) em espera retomado(s)", len(novos))
    notify(
        "estudo_retomando",
        f"Sessao do NotebookLM OK - {len(novos)} estudo(s) em espera "
        f"retomado(s)",
        level="info",
    )
    _evento.set()
    return len(novos)


# ---------------------------------------------------------------------
# API para o painel (indicadores, diagnostico e renovacao do login)
# ---------------------------------------------------------------------
def status() -> Dict[str, Any]:
    """Leitura barata do estado - o painel e o MQTT podem consultar a
    qualquer momento sem tocar na rede."""
    with _trava_saude:
        saude = dict(_saude)
    with _trava_fila:
        pendentes = len(_aguardando)
        fila = len(_fila)
        motivo = _motivo
    if not ligado():
        return {
            "ativo": False,
            "estado": "desconhecido",
            "detalhe": "estudo nao configurado neste equipamento",
            "verificado_em": saude.get("verificado_em", 0.0),
            "aguardando": 0,
            "motivo": "",
            "fila": fila,
        }
    return {
        "ativo": True,
        "estado": saude.get("estado", "desconhecido"),
        "detalhe": saude.get("detalhe", ""),
        "verificado_em": saude.get("verificado_em", 0.0),
        "aguardando": pendentes,
        "motivo": motivo,
        "fila": fila,
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


def iniciar() -> None:
    """Periodo de saude da sessao (chamado na subida do painel).

    Moderado de proposito: um passeio a cada 20 minutos (cadencia
    recomendada pelo proprio CLI para uso desassistido). A verificacao e
    somente leitura; falha de rede nao invalida nada (o ultimo estado
    conhecido permanece); com a sessao confirmada valida roda o
    keepalive oficial e retoma o que estiver em espera. Com a sessao
    morta, o vigia NAO tenta renovar em loop - renovacao acontece no
    disparo (uma vez) ou no botao.
    """
    global _vigia
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
            # auth: so atualiza o indicador; a renovacao acontece no
            # disparo ou no botao, nunca em loop
        except Exception:  # noqa: BLE001 - o vigia nunca morre
            log.exception("falha no periodo de saude do NotebookLM")


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
    with _trava_fila:
        if caminho in _fila or caminho in _aguardando:
            return
        _fila.append(caminho)
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
        while True:
            with _trava_fila:
                if not _fila:
                    break
                caminho = _fila.popleft()
            try:
                _rodar(caminho)
            except Exception as exc:  # noqa: BLE001 - o trabalhador nunca morre
                log.error("falha ao disparar estudo para %s: %s", caminho, exc)
                notify(
                    "estudo_erro",
                    f"Falha ao disparar o estudo: {exc}",
                    level="error",
                )


def _rodar(caminho: str) -> None:
    python = _cfg("python")
    pasta = _cfg("pasta")
    if not python or not pasta:
        return
    alvo = Path(pasta)
    if not (alvo / "pipeline.py").exists():
        log.warning("pipeline.py nao encontrado em %s - estudo nao disparado", alvo)
        notify(
            "estudo_erro",
            "Pipeline do estudo nao encontrado (sermon-pipeline)",
            level="error",
        )
        return

    # ---- pre-flight da sessao: preserva o job em vez de quebrar ------
    estado = verificar_saude(force=True)
    if estado == "auth":
        log.warning("sessao do NotebookLM expirada - uma tentativa de renovacao")
        if _renovar_sessao():
            _definir("ok", "sessao renovada automaticamente")
            estado = "ok"
    if estado == "auth":
        _aguardar(caminho, "autenticacao expirada")
        return
    if estado == "rede":
        # sem conexao o pipeline tambem quebraria: guarda o MP3 e o
        # periodo de saude devolve o job quando a rede voltar
        _aguardar(caminho, "sem rede")
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
        codigo = proc.wait()

    if codigo == 0:
        log.info("estudo concluido (%s)", arquivo_log.name)
        notify(
            "estudo_pronto",
            "Estudo gerado e enviado por WhatsApp",
            level="success",
        )
    else:
        log.error("pipeline terminou com codigo %s (%s)", codigo, arquivo_log)
        notify(
            "estudo_erro",
            f"Pipeline do estudo terminou com erro (codigo {codigo}) - "
            f"veja {arquivo_log.name}",
            level="error",
        )
