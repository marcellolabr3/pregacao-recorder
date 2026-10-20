"""Renovacao interativa isolada: sem navegador, CLI, rede ou pipeline reais."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import estudos
from app.db import Database


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    pipeline = tmp_path / "Pipeline com espacos"
    pipeline.mkdir()
    program = pipeline / "notebooklm.exe"
    program.write_text("", encoding="utf-8")
    values = {
        "estudos.ativo": True,
        "estudos.python": str(pipeline / "python.exe"),
        "estudos.pasta": str(pipeline),
        "estudos.notebooklm": str(program),
        "estudos.browser": "msedge",
    }
    monkeypatch.setattr(estudos.config, "get", lambda key, default=None: values.get(key, default))
    database = Database(tmp_path / "login-test.db")
    monkeypatch.setattr(estudos, "db", database)
    monkeypatch.setattr(estudos, "_login", {
        "em_andamento": False, "estado": "ocioso", "detalhe": "",
        "iniciado_em": 0.0, "finalizado_em": 0.0, "retomados": 0,
    })
    monkeypatch.setattr(estudos, "_saude", {
        "estado": "auth", "detalhe": "sessao expirada", "verificado_em": 0.0,
    })
    monkeypatch.setattr(estudos, "_ultima_renovacao", 0.0)
    monkeypatch.setattr(estudos, "_login_thread", None)
    monkeypatch.setattr(estudos, "_evento", threading.Event())
    monkeypatch.setattr(estudos, "_trava_nlm", threading.RLock())
    monkeypatch.setattr(estudos, "_trava_login", threading.RLock())
    notifications = []
    workers = []
    tasks = []
    monkeypatch.setattr(estudos, "notify", lambda kind, *a, **k: notifications.append(kind))
    monkeypatch.setattr(estudos, "_iniciar", lambda: workers.append(True))
    monkeypatch.setattr(estudos, "iniciar", lambda: None)

    class DeferredThread:
        def __init__(self, target, args=(), kwargs=None, daemon=False, **options):
            self.target, self.args, self.kwargs = target, args, kwargs or {}
            self.daemon = daemon
            self.done = False

        def start(self):
            tasks.append(self)

        def run(self):
            try:
                self.target(*self.args, **self.kwargs)
            finally:
                self.done = True

        def is_alive(self):
            return not self.done

    real_thread = threading.Thread
    monkeypatch.setattr(estudos.threading, "Thread", DeferredThread)

    def unexpected(*_args, **_kwargs):
        pytest.fail("nenhum subprocesso real e permitido neste teste")

    monkeypatch.setattr(estudos.subprocess, "Popen", unexpected)
    monkeypatch.setattr(estudos.subprocess, "run", unexpected)
    return SimpleNamespace(pipeline=pipeline, program=program, db=database,
                           tasks=tasks, notifications=notifications,
                           workers=workers, monkeypatch=monkeypatch, values=values,
                           real_thread=real_thread)


def waiting_job(scenario):
    audio = str(scenario.pipeline / "gravacao-preservada.mp3")
    assert scenario.db.create_job(audio, metadados={"tema": "preservar"})
    job = scenario.db.claim_job()
    assert scenario.db.job_aguardar(job["job_id"], "autenticacao expirada")
    return scenario.db.get_job(job["job_id"])


def fake_login(scenario, exit_code=0, health=(0, "all checks passed")):
    spawned, probes, observations = [], [], []
    waited = {"done": False}

    class Process:
        def wait(self, *a, **k):
            observations.append(estudos.status()["login"])
            waited["done"] = True
            return exit_code

    def popen(command, **kwargs):
        spawned.append((list(command), kwargs))
        observations.append(estudos.status()["login"])
        return Process()

    def probe(command, cwd, timeout):
        assert waited["done"], "nao verificar sessao antes de o login terminar"
        observations.append(estudos.status()["login"])
        probes.append((list(command), cwd, timeout))
        return health

    scenario.monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    scenario.monkeypatch.setattr(estudos, "_executar_nlm", probe)
    return SimpleNamespace(spawned=spawned, probes=probes, observations=observations)


def test_login_novo_e_monitorado_e_so_retoma_apos_prova_passiva(scenario):
    before = waiting_job(scenario)
    cli = fake_login(scenario)
    result = estudos.reconectar()
    assert result["lancado"] is True
    assert result["em_andamento"] is True
    assert result["login"]["em_andamento"] is True
    assert len(scenario.tasks) == 1 and scenario.tasks[0].daemon
    assert cli.spawned == []  # a requisicao HTTP nao aguarda o navegador
    assert scenario.db.get_job(before["job_id"]) == before
    scenario.tasks[0].run()
    command, options = cli.spawned[0]
    assert command == [str(scenario.program), "login", "--browser", "msedge",
                       "--fresh", "--browser-timeout", "600"]
    assert Path(options["cwd"]) == scenario.pipeline
    assert options["stdin"] == estudos.subprocess.DEVNULL
    assert options["creationflags"] == (estudos.subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert options["stdout"].name.endswith("login_nlm.log")
    assert cli.probes == [([str(scenario.program), "auth", "check", "--test", "--passive"],
                           scenario.pipeline, 60)]
    assert all(item["em_andamento"] for item in cli.observations)
    assert any(item["estado"] == "verificando" for item in cli.observations)
    status = estudos.status()
    assert status["estado"] == "ok"
    assert status["login"]["estado"] == "concluido"
    assert status["login"]["em_andamento"] is False
    assert status["login"]["retomados"] == 1
    assert status["login"]["finalizado_em"] >= status["login"]["iniciado_em"] > 0
    after = scenario.db.get_job(before["job_id"])
    assert after["estado"] == "PENDENTE"
    assert after["audio_path"] == before["audio_path"]
    assert after["metadados"] == before["metadados"]
    assert scenario.workers == [True]
    assert estudos._evento.is_set()


@pytest.mark.parametrize("exit_code,health", [
    (0, (1, "Authentication expired. Run notebooklm login.")),
    (0, (None, "timeout")),
    (1, (0, "all checks passed")),
])
def test_saida_zero_sozinha_e_cancelamento_nao_liberam_jobs(scenario, exit_code, health):
    before = waiting_job(scenario)
    cli = fake_login(scenario, exit_code=exit_code, health=health)
    estudos.reconectar()
    scenario.tasks[0].run()
    current = estudos.status()
    assert current["login"]["em_andamento"] is False
    assert current["login"]["estado"] == "erro"
    assert current["login"]["retomados"] == 0
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []
    assert "estudo_retomando" not in scenario.notifications
    if exit_code == 0:
        assert len(cli.probes) == 1


def test_cliques_repetidos_nao_abrem_outro_login_ativo(scenario):
    fake_login(scenario)
    first = estudos.reconectar()
    second = estudos.reconectar()
    assert first["lancado"] is True
    assert second["lancado"] is False
    assert second["em_andamento"] is True
    assert len(scenario.tasks) == 1
    scenario.tasks[0].run()
    third = estudos.reconectar()
    assert third["lancado"] is True
    assert len(scenario.tasks) == 2


def test_falha_ao_abrir_login_nao_expoe_excecao_nem_modifica_jobs(scenario):
    before = waiting_job(scenario)

    def failed(*a, **k):
        raise OSError("segredo-sintetico-nao-expor")

    scenario.monkeypatch.setattr(estudos.subprocess, "Popen", failed)
    estudos.reconectar()
    scenario.tasks[0].run()
    current = estudos.status()
    assert current["login"]["estado"] == "erro"
    assert current["login"]["em_andamento"] is False
    assert "segredo-sintetico" not in json.dumps(current)
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []


def test_login_em_andamento_suspende_checks_refresh_e_retomadas(scenario):
    before = waiting_job(scenario)
    estudos.reconectar()  # thread fica agendada, com o perfil em uso
    assert estudos._login_ativo() is True
    assert estudos.verificar_saude(force=True) == "auth"
    assert estudos._renovar_sessao() is False
    estudos._keepalive()
    result = estudos.diagnosticar()
    assert result["login"]["em_andamento"] is True
    assert result.get("retomados", 0) == 0
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []


def test_saude_confirmada_depois_da_falha_remove_erro_antigo_do_painel(scenario):
    before = waiting_job(scenario)
    fake_login(scenario, health=(1, "Authentication expired"))
    estudos.reconectar()
    scenario.tasks[0].run()
    failure = estudos.status()["login"]
    assert failure["estado"] == "erro"
    scenario.monkeypatch.setattr(estudos, "_executar_nlm", lambda *a, **k: (0, "all checks passed"))
    assert estudos.verificar_saude(force=True) == "ok"
    recovered = estudos.status()
    assert recovered["estado"] == "ok"
    assert recovered["login"]["estado"] == "concluido"
    assert recovered["login"]["em_andamento"] is False
    assert recovered["login"]["detalhe"] != failure["detalhe"]
    assert recovered["login"]["finalizado_em"] >= failure["finalizado_em"]
    # Provar saude e retomar jobs sao etapas distintas; este probe nao executa fila.
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []


@pytest.mark.parametrize("stale_health", ["auth", "rede"])
def test_login_concluido_entre_preflight_e_espera_nao_deixa_job_parado(scenario, stale_health):
    (scenario.pipeline / "pipeline.py").write_text("# pipeline simulado", encoding="utf-8")
    audio = str(scenario.pipeline / "audio-preservado.mp3")
    scenario.db.create_job(audio)
    job = scenario.db.claim_job()
    estudos._login.update(em_andamento=True, estado="aguardando")
    spawned = []

    def preflight(force=False):
        # O monitor confirma o login quando este job ainda esta EXECUTANDO:
        # sua retomada nao encontra o job, que nao chegou a entrar em espera.
        assert scenario.db.get_job(job["job_id"])["estado"] == "EXECUTANDO"
        with estudos._trava_login:
            estudos._login.update(em_andamento=False, estado="concluido")
            estudos._definir("ok", "sessao confirmada pelo monitor")
            assert estudos._retomar_pendentes() == 0
        # O worker recebe agora o resultado anterior ao termino do login.
        return stale_health

    class Pipeline:
        def poll(self):
            return 0

        def wait(self):
            return 0

    def popen(command, **options):
        spawned.append(list(command))
        options["stdout"].write("=== CONCLUIDO\n")
        options["stdout"].flush()
        return Pipeline()

    scenario.monkeypatch.setattr(estudos, "verificar_saude", preflight)
    scenario.monkeypatch.setattr(estudos, "_renovar_sessao", lambda: False)
    scenario.monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    estudos._rodar(job)
    after = scenario.db.get_job(job["job_id"])
    assert after["estado"] == "CONCLUIDO"
    assert after["audio_path"] == audio
    assert len(spawned) == 1 and spawned[0][1] == "pipeline.py"
    assert audio in spawned[0]
    assert scenario.db.job_contagens().get("AGUARDANDO_INTERVENCAO", 0) == 0
    assert "estudo_aguardando_auth" not in scenario.notifications
    assert "estudo_aguardando_rede" not in scenario.notifications


@pytest.mark.parametrize("active,login_state,health", [
    (True, "aguardando", "ok"),
    (False, "erro", "auth"),
])
def test_preflight_nao_libera_pipeline_com_login_ativo_ou_falho(scenario, active, login_state, health):
    (scenario.pipeline / "pipeline.py").write_text("# pipeline simulado", encoding="utf-8")
    audio = str(scenario.pipeline / "audio-em-espera.mp3")
    scenario.db.create_job(audio)
    job = scenario.db.claim_job()
    estudos._login.update(em_andamento=active, estado=login_state)
    estudos._saude.update(estado=health)
    scenario.monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "auth")
    scenario.monkeypatch.setattr(estudos, "_renovar_sessao", lambda: False)
    # Popen/run continuam bloqueados pelo fixture: qualquer pipeline/CLI falha.
    estudos._rodar(job)
    after = scenario.db.get_job(job["job_id"])
    assert after["estado"] == "AGUARDANDO_INTERVENCAO"
    assert after["motivo"] == "autenticacao expirada"
    assert after["audio_path"] == audio
    assert "estudo_aguardando_auth" in scenario.notifications
    assert scenario.workers == []


def test_login_iniciado_apos_probe_ok_pausa_job_antes_do_pipeline(scenario):
    (scenario.pipeline / "pipeline.py").write_text("# pipeline simulado", encoding="utf-8")
    audio = str(scenario.pipeline / "audio-do-novo-login.mp3")
    scenario.db.create_job(audio)
    job = scenario.db.claim_job()
    estudos._saude.update(estado="ok")

    def preflight(force=False):
        # A consulta comecou antes de haver login, mas o clique chega antes
        # de o worker decidir iniciar o pipeline usando aquele resultado.
        assert not estudos._login_ativo()
        assert estudos.reconectar()["lancado"] is True
        return "ok"

    scenario.monkeypatch.setattr(estudos, "verificar_saude", preflight)
    estudos._rodar(job)
    assert len(scenario.tasks) == 1
    assert estudos._login_ativo() is True
    after = scenario.db.get_job(job["job_id"])
    assert after["estado"] == "AGUARDANDO_INTERVENCAO"
    assert after["motivo"] == "autenticacao expirada"
    assert after["audio_path"] == audio
    assert scenario.workers == []


@pytest.mark.parametrize("failure", [None, "popen", "monitor"])
def test_clique_apos_guarda_e_antes_popen_aguarda_pipeline_e_libera_perfil(scenario, failure):
    """O login usa outra thread real; nenhum processo ou conta real e aberto."""
    (scenario.pipeline / "pipeline.py").write_text("# pipeline simulado", encoding="utf-8")
    audio = str(scenario.pipeline / "audio-da-corrida.mp3")
    scenario.db.create_job(audio, metadados={"tema": "preservar"})
    job = scenario.db.claim_job()
    scenario.monkeypatch.setattr(estudos, "verificar_saude", lambda force=False: "ok")
    scenario.monkeypatch.setattr(estudos, "_executar_nlm", lambda *a, **k: (0, "all checks passed"))
    login_attempted = threading.Event()
    login_acquired = threading.Event()
    pipeline_finished = threading.Event()
    profile_lock = threading.RLock()
    threads, events = [], []

    class ObservedProfile:
        def __enter__(self):
            login_thread = threading.current_thread().name == "login-concorrente"
            if login_thread:
                login_attempted.set()
            profile_lock.acquire()
            if login_thread:
                login_acquired.set()
            return self

        def __exit__(self, *_args):
            profile_lock.release()

    scenario.monkeypatch.setattr(estudos, "_trava_nlm", ObservedProfile())

    def notify(kind, *_args, **_kwargs):
        scenario.notifications.append(kind)
        if kind == "estudo_iniciando":
            # Este aviso ocorre depois da ultima guarda e antes de Popen.
            result = estudos.reconectar()
            assert result["lancado"] is True
            thread = scenario.real_thread(target=scenario.tasks[0].run,
                                          name="login-concorrente", daemon=True)
            threads.append(thread)
            thread.start()
            assert login_attempted.wait(2)
            assert not login_acquired.wait(0.05), "login abriu antes de o pipeline liberar o perfil"

    scenario.monkeypatch.setattr(estudos, "notify", notify)

    class Pipeline:
        def poll(self):
            return 0

        def wait(self):
            events.append("pipeline_fim")
            pipeline_finished.set()
            return 0

    class Login:
        def wait(self):
            return 0

    def popen(command, **options):
        if command[1] == "pipeline.py":
            assert not login_acquired.is_set()
            events.append("pipeline")
            if failure == "popen":
                pipeline_finished.set()
                raise OSError("falha sintetica ao abrir pipeline")
            options["stdout"].write("=== CONCLUIDO\n")
            options["stdout"].flush()
            return Pipeline()
        assert command[1] == "login"
        assert pipeline_finished.is_set(), "login e pipeline disputaram o perfil"
        events.append("login")
        return Login()

    scenario.monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    if failure == "monitor":
        def failed_monitor(*_args, **_kwargs):
            raise RuntimeError("falha sintetica ao ler progresso")

        scenario.monkeypatch.setattr(estudos, "_drenar_log", failed_monitor)
    try:
        if failure:
            with pytest.raises(OSError if failure == "popen" else RuntimeError):
                estudos._rodar(job)
        else:
            estudos._rodar(job)
    finally:
        for thread in threads:
            thread.join(2)
    assert threads and all(not thread.is_alive() for thread in threads)
    assert events == (["pipeline", "login"] if failure == "popen" else
                      ["pipeline", "pipeline_fim", "login"])
    assert estudos.status()["login"]["estado"] == "concluido"
    after = scenario.db.get_job(job["job_id"])
    assert after["audio_path"] == job["audio_path"]
    assert after["metadados"] == job["metadados"]
    if not failure:
        assert after["estado"] == "CONCLUIDO"


def test_login_ja_executando_preserva_job_sem_esperar_navegador(scenario):
    (scenario.pipeline / "pipeline.py").write_text("# pipeline simulado", encoding="utf-8")
    scenario.db.create_job(str(scenario.pipeline / "audio-antes-do-login.mp3"))
    job = scenario.db.claim_job()
    login_opened, finish_login = threading.Event(), threading.Event()

    class Login:
        def wait(self):
            assert finish_login.wait(2)
            return 0

    def popen(command, **_kwargs):
        assert command[1] == "login", "pipeline nao pode abrir enquanto ha login"
        login_opened.set()
        return Login()

    scenario.monkeypatch.setattr(estudos.subprocess, "Popen", popen)
    scenario.monkeypatch.setattr(estudos, "_executar_nlm", lambda *a, **k: (0, "all checks passed"))
    estudos.reconectar()
    thread = scenario.real_thread(target=scenario.tasks[0].run, daemon=True)
    thread.start()
    try:
        assert login_opened.wait(2)
        estudos._rodar(job)
        paused = scenario.db.get_job(job["job_id"])
        assert paused["estado"] == "AGUARDANDO_INTERVENCAO"
        assert paused["audio_path"] == job["audio_path"]
        assert not finish_login.is_set()
    finally:
        finish_login.set()
        thread.join(2)
    assert not thread.is_alive()
    resumed = scenario.db.get_job(job["job_id"])
    assert resumed["estado"] == "PENDENTE"
    assert resumed["job_id"] == job["job_id"]


@pytest.mark.parametrize("configured", [True, False])
def test_status_inclui_snapshot_do_login_sem_cli(scenario, configured):
    scenario.monkeypatch.setattr(estudos, "ligado", lambda: configured)
    current = estudos.status()
    assert "login" in current
    assert current["login"]["em_andamento"] is False
    current["login"]["em_andamento"] = True
    assert estudos.status()["login"]["em_andamento"] is False


def test_endpoint_exige_admin_e_nao_multiplica_login(scenario, monkeypatch):
    from flask import Flask
    from app.api import routes

    monkeypatch.setenv("PREGACAO_PIN", "1234")
    monkeypatch.setenv("PREGACAO_ADMIN_PIN", "5678")
    monkeypatch.setattr(routes, "_registra_agente", lambda: None)
    app = Flask("login-test")
    app.config.update(SECRET_KEY="segredo-de-teste", TESTING=True)
    routes.register_routes(app, SimpleNamespace(), SimpleNamespace())
    with app.test_client() as client:
        assert client.post("/api/estudos/reconectar").status_code == 401
        assert scenario.tasks == []
        with client.session_transaction() as session:
            session["auth"] = True
        assert client.post("/api/estudos/reconectar").status_code == 403
        assert scenario.tasks == []
        with client.session_transaction() as session:
            session["admin"] = True
        first = client.post("/api/estudos/reconectar")
        second = client.post("/api/estudos/reconectar")
        assert first.status_code == second.status_code == 200
        assert first.get_json()["lancado"] is True
        assert second.get_json()["lancado"] is False
        assert len(scenario.tasks) == 1


# O pacote inclui NotebookLM como modulo do Python privado, sem .venv/launchers.
def _runtime_embutido(scenario):
    scenario.values.pop("estudos.notebooklm")
    scenario.values.pop("estudos.browser")
    scenario.monkeypatch.setattr(estudos.bundled_runtime, "is_bundled", lambda: True)
    return [estudos.sys.executable, "-m", "notebooklm"]


def test_cli_fora_do_pacote_preserva_venv_mesmo_com_env_bundled(scenario):
    scenario.values.pop("estudos.notebooklm")
    scenario.values.pop("estudos.browser")
    scenario.monkeypatch.setenv("PREGACAO_BUNDLED_ROOT", str(scenario.pipeline))
    # Uma variavel de ambiente sozinha nao transforma fontes em pacote valido.
    assert estudos.bundled_runtime.is_bundled() is False
    directory = "Scripts" if os.name == "nt" else "bin"
    filename = "notebooklm.exe" if os.name == "nt" else "notebooklm"
    program = str(scenario.pipeline / ".venv" / directory / filename)
    assert estudos._nlm_programa(str(scenario.pipeline)) == program
    assert estudos._nlm_prefixo(str(scenario.pipeline)) == [program]
    assert estudos._nlm_navegador() == "msedge"


def test_probe_no_pacote_usa_modulo_sem_venv(scenario):
    prefix = _runtime_embutido(scenario)
    probes = []

    def probe(command, cwd, timeout):
        probes.append((command, cwd, timeout))
        return 0, "all checks passed"

    scenario.monkeypatch.setattr(estudos, "_executar_nlm", probe)
    assert not (scenario.pipeline / ".venv").exists()
    assert estudos._nlm_programa(str(scenario.pipeline)) == estudos.sys.executable
    assert estudos._programa_existe(estudos._nlm_programa(str(scenario.pipeline)))
    assert estudos.verificar_saude(force=True) == "ok"
    assert probes == [(prefix + ["auth", "check", "--test", "--passive"],
                       scenario.pipeline, 60)]


def test_login_no_pacote_usa_chromium_e_confirma_com_mesmo_modulo(scenario):
    prefix = _runtime_embutido(scenario)
    before = waiting_job(scenario)
    cli = fake_login(scenario)
    result = estudos.reconectar()
    assert result["navegador"] == "chromium"
    assert scenario.db.get_job(before["job_id"]) == before
    scenario.tasks[0].run()
    command, options = cli.spawned[0]
    assert command == prefix + ["login", "--browser", "chromium", "--fresh",
                                "--browser-timeout", "600"]
    assert Path(options["cwd"]) == scenario.pipeline
    assert cli.probes == [(prefix + ["auth", "check", "--test", "--passive"],
                           scenario.pipeline, 60)]
    assert estudos.status()["login"]["estado"] == "concluido"
    assert scenario.db.get_job(before["job_id"])["estado"] == "PENDENTE"


@pytest.mark.parametrize("browser", [None, "msedge"])
@pytest.mark.parametrize("exit_code", [0, 1, None])
def test_refresh_no_pacote_usa_perfil_dedicado_e_respeita_resultado_e_cadencia(
    scenario, browser, exit_code
):
    prefix = _runtime_embutido(scenario)
    if browser:
        scenario.values["estudos.browser"] = browser
    before = waiting_job(scenario)
    calls = []

    def refresh(command, cwd, timeout):
        calls.append((command, cwd, timeout))
        return exit_code, "sessao renovada" if exit_code == 0 else "login necessario"

    scenario.monkeypatch.setattr(estudos, "_executar_nlm", refresh)
    assert estudos._renovar_sessao() is (exit_code == 0)
    assert calls == [(prefix + ["auth", "refresh", "--allow-headless", "--verify"],
                      scenario.pipeline, 300)]
    assert estudos._renovar_sessao() is False
    assert len(calls) == 1
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []


@pytest.mark.parametrize("browser,cookie_browser", [("msedge", "edge"), ("chrome", "chrome")])
@pytest.mark.parametrize("exit_codes", [(0,), (1, 0), (1, 1)])
def test_refresh_em_desenvolvimento_preserva_browser_fallback_e_resultado(
    scenario, browser, cookie_browser, exit_codes
):
    scenario.monkeypatch.setattr(estudos.bundled_runtime, "is_bundled", lambda: False)
    scenario.values["estudos.browser"] = browser
    before = waiting_job(scenario)
    calls = []

    def refresh(command, cwd, timeout):
        calls.append((command, cwd, timeout))
        code = exit_codes[len(calls) - 1]
        return code, "sessao renovada" if code == 0 else "login necessario"

    scenario.monkeypatch.setattr(estudos, "_executar_nlm", refresh)
    assert estudos._renovar_sessao() is (exit_codes[-1] == 0)
    expected = [([str(scenario.program), "auth", "refresh", "--browser-cookies",
                 cookie_browser, "--verify"], scenario.pipeline, 300)]
    if len(exit_codes) == 2:
        expected.append(([str(scenario.program), "auth", "refresh", "--allow-headless",
                          "--verify"], scenario.pipeline, 300))
    assert calls == expected
    assert scenario.db.get_job(before["job_id"]) == before
    assert scenario.workers == []


def test_keepalive_no_pacote_usa_modulo_e_respeita_cadencia(scenario):
    prefix = _runtime_embutido(scenario)
    calls = []

    def refresh(command, cwd, timeout):
        calls.append((command, cwd, timeout))
        return 0, "sessao confirmada"

    scenario.monkeypatch.setattr(estudos, "_executar_nlm", refresh)
    estudos._keepalive()
    estudos._keepalive()
    assert calls == [(prefix + ["auth", "refresh", "--verify"], scenario.pipeline, 120)]


@pytest.mark.parametrize("extension", [".exe", ".cmd"])
def test_override_cli_e_browser_no_pacote_continua_explicito(scenario, extension):
    scenario.monkeypatch.setattr(estudos.bundled_runtime, "is_bundled", lambda: True)
    program = scenario.pipeline / ("meu-notebooklm" + extension)
    program.write_text("", encoding="utf-8")
    scenario.values["estudos.notebooklm"] = str(program)
    scenario.values["estudos.browser"] = "msedge"
    assert estudos._nlm_programa(str(scenario.pipeline)) == str(program)
    assert estudos._nlm_prefixo(str(scenario.pipeline)) == [str(program)]
    cli = fake_login(scenario)
    assert estudos.reconectar()["navegador"] == "msedge"
    scenario.tasks[0].run()
    prefix = ["cmd", "/c", str(program)] if extension == ".cmd" else [str(program)]
    assert cli.spawned[0][0] == prefix + ["login", "--browser", "msedge", "--fresh",
                                        "--browser-timeout", "600"]
    assert cli.probes[0][0] == [str(program), "auth", "check", "--test", "--passive"]
