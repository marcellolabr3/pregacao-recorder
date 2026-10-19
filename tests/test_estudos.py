# Estudo automatico: a fila que liga o gravador ao sermon-pipeline.
import os
import time
from pathlib import Path

import pytest

from app import estudos
from app.db import Database


@pytest.fixture(autouse=True)
def _db_isolado(monkeypatch, tmp_path):
    """Cada teste com seu proprio banco: a fila e persistente (S2)."""
    monkeypatch.setattr(estudos, "db", Database(tmp_path / "jobs.db"))


class _Proc:
    def __init__(self, spy, codigo=0, stdout=None):
        self._spy = spy
        self._codigo = codigo
        if codigo == 0 and stdout is not None:
            # espelho dos marcos reais do pipeline para a drenagem do log
            stdout.write("=== 8. Enviando PDF\n=== CONCLUIDO\n")
            stdout.flush()

    def wait(self):
        return self._codigo

    def poll(self):
        return self._codigo


def _config_falsa(monkeypatch, **chaves):
    valores = {
        "estudos.ativo": True,
        "estudos.python": "C:/venv/python.exe",
        "estudos.pasta": "C:/pipeline",
        "estudos.whatsapp": "",
    }
    valores.update(chaves)

    def get(chave, padrao=None):
        return valores.get(chave, padrao)

    monkeypatch.setattr(estudos.config, "get", get)


def _espera(chamadas, timeout=5.0):
    limite = time.time() + timeout
    while time.time() < limite:
        concluido = chamadas() if callable(chamadas) else chamadas
        if concluido:
            return True
        time.sleep(0.02)
    return False


def _pipeline_no(monkeypatch, tmp_path):
    (tmp_path / "pipeline.py").write_text("#", encoding="utf-8")
    return tmp_path


def test_sem_config_nao_dispara_nada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess, "Popen",
        lambda *a, **k: chamadas.append(a) or _Proc(chamadas),
    )
    # equipamento sem nenhum "estudos" configurado
    monkeypatch.setattr(
        estudos.config, "get", lambda chave, padrao=None: padrao
    )
    estudos.enfileirar("C:/audio.mp3")
    time.sleep(0.2)
    assert chamadas == []
    assert not estudos.ligado()


def test_dispara_pipeline_com_skip_drive_e_numero(monkeypatch, tmp_path):
    pasta = _pipeline_no(monkeypatch, tmp_path)
    _config_falsa(
        monkeypatch,
        **{
            "estudos.python": "/venv/python.exe",
            "estudos.pasta": str(pasta),
            "estudos.whatsapp": "5521999999999",
        },
    )
    chamadas = []
    kwargs = {}

    def popen(cmd, **kw):
        chamadas.append(cmd)
        kwargs.update(kw)
        return _Proc(chamadas)

    monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(chamadas)
    assert chamadas[0] == [
        "/venv/python.exe",
        "pipeline.py",
        str(tmp_path / "pregacao.mp3"),
        "--skip-drive",
        "--to",
        "5521999999999",
    ]
    assert kwargs["cwd"] == str(pasta)
    # log do handoff gravado dentro do proprio sermon-pipeline
    logs = list((pasta / "logs").glob("handoff_*.log"))
    assert logs and "pregacao.mp3" in logs[0].read_text(encoding="utf-8")


def test_sem_numero_usa_padrao_do_pipeline(monkeypatch, tmp_path):
    pasta = _pipeline_no(monkeypatch, tmp_path)
    _config_falsa(
        monkeypatch,
        **{"estudos.python": "/venv/python.exe", "estudos.pasta": str(pasta)},
    )
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    estudos.enfileirar("pregacao.mp3")
    assert _espera(chamadas)
    assert "--to" not in chamadas[0]


def test_ativo_falso_nao_dispara(monkeypatch, tmp_path):
    pasta = _pipeline_no(monkeypatch, tmp_path)
    _config_falsa(
        monkeypatch,
        **{
            "estudos.ativo": False,
            "estudos.python": "/venv/python.exe",
            "estudos.pasta": str(pasta),
        },
    )
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    estudos.enfileirar("pregacao.mp3")
    time.sleep(0.2)
    assert chamadas == []


def test_pipeline_inexistente_avisa(monkeypatch, tmp_path):
    pasta = tmp_path / "sem-pipeline"
    pasta.mkdir()
    _config_falsa(
        monkeypatch,
        **{"estudos.python": "/venv/python.exe", "estudos.pasta": str(pasta)},
    )
    chamadas = []
    avisos = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: avisos.append(a[0] if a else "")
    )
    estudos.enfileirar("pregacao.mp3")
    time.sleep(0.3)
    assert chamadas == []
    # alem do aviso, o marco vermelho do job tambem e publicado (S3)
    assert avisos and "estudo_erro" in avisos
    assert "job_progress" in avisos
    # o job nao some: fica registrado como ERRO com o motivo
    job = estudos.db.list_jobs(1)[0]
    assert job["estado"] == "ERRO"
    assert "pipeline.py" in job["erro"]


# ---------------------------------------------------------------------
# saude da sessao do NotebookLM (pre-flight, espera e retomada)
# ---------------------------------------------------------------------
def _limpa():
    """Estado do modulo zerado entre testes (o banco vem do fixture
    _db_isolado: um jobs.db novo por teste)."""
    estudos._ultima_renovacao = 0.0
    with estudos._trava_saude:
        estudos._saude.update(
            {
                "estado": "desconhecido",
                "detalhe": "ainda nao verificado",
                "verificado_em": 0.0,
            }
        )


def _nlm_falso(tmp_path):
    """Um 'notebooklm instalado': so precisa existir, as chamadas sao
    substituidas por _respostas_nlm."""
    nome = "notebooklm.exe" if os.name == "nt" else "notebooklm"
    prog = tmp_path / nome
    prog.write_text("", encoding="utf-8")
    return prog


def _respostas_nlm(monkeypatch, check, refresh=(0, "")):
    """Substitui o CLI por respostas fixas; devolve a lista de comandos."""
    chamadas = []

    def run(cmd, **kw):
        eh_refresh = "refresh" in list(cmd)
        codigo, texto = refresh if eh_refresh else check
        chamadas.append(list(cmd))

        class _ProcFake:
            pass

        proc = _ProcFake()
        proc.returncode = codigo
        proc.stdout = texto
        proc.stderr = ""
        return proc

    monkeypatch.setattr(estudos.subprocess, "run", run)
    return chamadas


def _cenario(monkeypatch, tmp_path, **extra):
    _limpa()
    pasta = _pipeline_no(monkeypatch, tmp_path)
    prog = _nlm_falso(tmp_path)
    _config_falsa(
        monkeypatch,
        **{
            "estudos.python": "/venv/python.exe",
            "estudos.pasta": str(pasta),
            "estudos.notebooklm": str(prog),
        },
        **extra,
    )
    avisos = []
    monkeypatch.setattr(
        estudos, "notify", lambda *a, **k: avisos.append(a[0] if a else "")
    )
    return pasta, avisos


def test_sessao_valida_dispara_normalmente(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    nlm = _respostas_nlm(monkeypatch, check=(0, "all checks passed"))
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(chamadas)
    assert chamadas[0][1] == "pipeline.py"
    assert any("auth" in c for c in nlm)  # o pre-flight aconteceu
    assert estudos.status()["aguardando"] == 0
    assert "estudo_aguardando_auth" not in avisos


def test_sessao_expirada_renovada_nao_pausa(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    nlm = _respostas_nlm(
        monkeypatch,
        check=(1, "Authentication expired. Run 'notebooklm login'."),
        refresh=(0, "sessao renovada"),
    )
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(chamadas)
    assert chamadas[0][1] == "pipeline.py"
    # sucesso na PRIMEIRA ordem oficial (extracao do navegador): so ela
    assert sum(1 for c in nlm if "refresh" in c) == 1
    assert estudos.status()["aguardando"] == 0
    assert "estudo_aguardando_auth" not in avisos


def test_sessao_expirada_sem_renovacao_preserva_o_job(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    nlm = _respostas_nlm(
        monkeypatch,
        check=(1, "Authentication expired. Run 'notebooklm login'."),
        refresh=(1, "The browser's Google session is signed out"),
    )
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    caminho = str(tmp_path / "pregacao.mp3")
    estudos.enfileirar(caminho)
    assert _espera(lambda: "estudo_aguardando_auth" in avisos)
    # o pipeline NUNCA foi disparado e o job fica guardado, com aviso
    assert chamadas == []
    assert "estudo_aguardando_auth" in avisos
    # as DUAS ordens oficiais foram tentadas uma unica vez, e falharam
    assert sum(1 for c in nlm if "refresh" in c) == 2
    st = estudos.status()
    assert st["aguardando"] == 1
    assert st["motivo"] == "autenticacao expirada"


def test_falha_de_rede_tambem_preserva_o_job(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    _respostas_nlm(monkeypatch, check=(1, "connection timed out"))
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    estudos.enfileirar(str(tmp_path / "pregacao.mp3"))
    assert _espera(lambda: "estudo_aguardando_rede" in avisos)
    assert chamadas == []
    assert "estudo_aguardando_rede" in avisos
    assert estudos.status()["motivo"] == "sem rede"


def test_sessao_volta_retoma_o_que_estava_em_espera(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    _respostas_nlm(monkeypatch, check=(0, "ok"))
    chamadas = []
    monkeypatch.setattr(
        estudos.subprocess,
        "Popen",
        lambda cmd, **kw: chamadas.append(cmd) or _Proc(chamadas),
    )
    # um job pausado por uma falha anterior + trabalhador devidamente no ar
    estudos.db.create_job(audio_path=str(tmp_path / "espera.mp3"))
    job = estudos.db.claim_job()
    estudos._aguardar(job["job_id"], "autenticacao expirada")
    estudos._iniciar()

    resultado = estudos.diagnosticar()
    assert resultado["retomados"] == 1
    assert "estudo_retomando" in avisos
    # o pipeline roda com o MESMO arquivo de audio (gravacao e upload
    # nao se repetem - so a parte do NotebookLM em diante)
    assert _espera(chamadas)
    assert chamadas[0][1] == "pipeline.py"
    assert str(tmp_path / "espera.mp3") in chamadas[0]
    assert estudos.status()["aguardando"] == 0
    assert estudos.status()["motivo"] == ""


def test_status_expoe_os_campos_do_painel(monkeypatch, tmp_path):
    _cenario(monkeypatch, tmp_path)
    st = estudos.status()
    for campo in ("ativo", "estado", "detalhe", "verificado_em",
                  "aguardando", "motivo", "fila"):
        assert campo in st
    assert st["ativo"] is True


def test_keepalive_oficial_respeita_a_cadencia(monkeypatch, tmp_path):
    _cenario(monkeypatch, tmp_path)
    nlm = _respostas_nlm(monkeypatch, check=(0, "ok"), refresh=(0, ""))
    estudos._keepalive()
    estudos._keepalive()  # logo em seguida: o intervalo minimo segura
    refreshes = [c for c in nlm if "refresh" in c]
    assert len(refreshes) == 1
    # keepalive PURO (a ordem oficial do CLI para cadencia) - a versao
    # --browser-cookies so existe no caminho de recuperacao, nunca aqui
    assert refreshes[0][1:4] == ["auth", "refresh", "--verify"]


def test_keepalive_nao_roda_com_sessao_morta(monkeypatch, tmp_path):
    _cenario(monkeypatch, tmp_path)
    nlm = _respostas_nlm(monkeypatch, check=(1, "Authentication expired"))
    # o vigia chama o keepalive SO com sessao viva; unitariamente a prova
    # e que ele nao e chamado de graca: sem chamada, zero renovacoes
    assert estudos.verificar_saude(force=True) == "auth"
    assert nlm and "refresh" not in " ".join(nlm[0])
    assert not any("refresh" in c for c in nlm)


def test_reconectar_agenda_login_monitorado_com_log(monkeypatch, tmp_path):
    pasta, avisos = _cenario(monkeypatch, tmp_path)
    _respostas_nlm(monkeypatch, check=(1, "Authentication expired"))
    chamadas = {}

    def popen(cmd, **kw):
        chamadas["cmd"] = list(cmd)
        chamadas["kw"] = kw
        return _Proc(chamadas)

    monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    r = estudos.reconectar()
    assert r["lancado"] is True
    assert r["navegador"] == "msedge"
    estudos._login_thread.join(timeout=5)
    assert not estudos._login_thread.is_alive()
    # Ocultar o console nao altera o navegador headed aberto pelo CLI.
    assert chamadas["cmd"][1:4] == ["login", "--browser", "msedge"]
    assert "--fresh" in chamadas["cmd"]
    assert chamadas["kw"].get("creationflags", 0) == (
        estudos.subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert estudos.status()["login"]["em_andamento"] is False
    # e a saida fica num log, para uma falha rapida nao sumir com o motivo
    log_nlm = pasta / "logs" / "login_nlm.log"
    assert log_nlm.exists() and "login" in log_nlm.read_text(encoding="utf-8")
