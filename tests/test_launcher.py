"""Inicializacao Windows isolada: nenhum servidor, MQTT ou captura reais."""
from __future__ import annotations

import copy
from contextlib import nullcontext
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import launcher


@pytest.fixture
def context(tmp_path, monkeypatch):
    root = tmp_path / "Projeto com espacos"
    home = tmp_path / "Dados preservados"
    root.mkdir()
    (home / "logs").mkdir(parents=True)
    env = {"PATH": "caminho-sintetico", "VAR_EXISTENTE": "preservada"}
    spawned = []
    ready = []
    agents = []
    child = SimpleNamespace(pid=4321, poll=lambda: None)

    def popen(command, **kwargs):
        spawned.append((command, kwargs))
        return child

    monkeypatch.setattr(launcher, "running_pid", lambda *_: None)
    monkeypatch.setattr(launcher, "_port_available", lambda *_: True)
    monkeypatch.setattr(launcher, "dependency_check", lambda *_: [])
    monkeypatch.setattr(launcher.shutil, "which", lambda *a, **k: "ffmpeg.exe")
    monkeypatch.setattr(launcher, "_creationflags", lambda: 0)
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher, "wait_ready", lambda *a, **k: ready.append((a, k)))
    monkeypatch.setattr(launcher, "_wait_agent", lambda *a, **k: agents.append((a, k)))
    return SimpleNamespace(root=root, home=home, env=env, spawned=spawned,
                           ready=ready, agents=agents, child=child,
                           url="http://127.0.0.1:18765")


def test_servidor_existente_e_reutilizado_sem_novo_processo(context, monkeypatch):
    monkeypatch.setattr(launcher, "running_pid", lambda *_: 321)
    assert launcher.launch("gravador", context.root, context.home,
                           context.env, context.url, 2) is False
    assert context.spawned == []
    assert len(context.ready) == 1


def test_agente_existente_e_reutilizado_sem_consultar_api(context, monkeypatch):
    monkeypatch.setattr(launcher, "running_pid", lambda *_: 322)
    assert launcher.launch("agente", context.root, context.home,
                           context.env, context.url, 2) is False
    assert context.spawned == []
    assert context.ready == []
    assert context.agents == []


def test_porta_ocupada_nao_dispara_backend(context, monkeypatch):
    monkeypatch.setattr(launcher, "_port_available", lambda *_: False)
    with pytest.raises(launcher.LaunchError):
        launcher.launch("gravador", context.root, context.home,
                        context.env, context.url, 2)
    assert context.spawned == []


def test_ffmpeg_ausente_nao_dispara_backend(context, monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda *a, **k: None)
    with pytest.raises(launcher.LaunchError):
        launcher.launch("gravador", context.root, context.home,
                        context.env, context.url, 2)
    assert context.spawned == []


def test_dependencia_ausente_nao_dispara_processo(context, monkeypatch):
    monkeypatch.setattr(launcher, "dependency_check", lambda *_: ["flask"])
    with pytest.raises(launcher.LaunchError):
        launcher.launch("gravador", context.root, context.home,
                        context.env, context.url, 2)
    assert context.spawned == []


def test_filhos_usam_mesmo_home_e_logs_separados_sem_mutar_ambiente(context):
    original = copy.deepcopy(context.env)
    assert launcher.launch("gravador", context.root, context.home,
                           context.env, context.url, 2) is True
    assert launcher.launch("agente", context.root, context.home,
                           context.env, context.url, 2) is True
    assert context.env == original
    assert len(context.spawned) == 2
    for (command, opts), component, logfile in zip(
        context.spawned, ("gravador", "agente"),
        ("pregacao.log", "pregacao-agente.log"),
    ):
        assert command == [launcher.sys.executable, "-B", "-m", "app.launcher",
                           "--service", component]
        assert Path(opts["cwd"]) == context.root
        assert Path(opts["env"]["PREGACAO_HOME"]) == context.home
        assert opts["env"]["PREGACAO_LOG_FILE"] == logfile
        assert opts["env"]["VAR_EXISTENTE"] == "preservada"
        assert opts["env"] is not context.env
        assert opts["stdin"] == subprocess.DEVNULL
        assert opts["stdout"] == subprocess.DEVNULL
        assert opts["stderr"] == subprocess.DEVNULL
        assert opts["close_fds"] is True
    assert len(context.ready) == 1
    assert len(context.agents) == 1


def test_falha_do_agente_nao_encerra_gravador_criado(context, monkeypatch):
    # O filho nao oferece terminate()/kill(): tentar encerrar o gravador falha.
    launcher.launch("gravador", context.root, context.home,
                    context.env, context.url, 2)

    def fail(*_args, **_kwargs):
        raise launcher.LaunchError("agente indisponivel")

    monkeypatch.setattr(launcher, "_wait_agent", fail)
    with pytest.raises(launcher.LaunchError):
        launcher.launch("agente", context.root, context.home,
                        context.env, context.url, 2)
    assert len(context.spawned) == 2


@pytest.mark.parametrize("component,module", [
    ("gravador", "app.main"), ("agente", "app.remote.agent"),
])
def test_pid_valido_identifica_modulo_esperado(tmp_path, monkeypatch, component, module):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [launcher.sys.executable, "-m", module])
    assert launcher.running_pid(pidfile, component) == 12345


@pytest.mark.parametrize("component", ["gravador", "agente"])
def test_pid_do_servico_do_launcher_e_reconhecido(tmp_path, monkeypatch, component):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        launcher.sys.executable, "-B", "-m", "app.launcher", "--service", component])
    assert launcher.running_pid(pidfile, component) == 12345


def test_pid_morto_nao_bloqueia_nova_inicializacao(tmp_path, monkeypatch):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: None)
    assert launcher.running_pid(pidfile, "gravador") is None


def test_pid_reutilizado_por_outro_programa_nao_e_aceito(tmp_path, monkeypatch):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [launcher.sys.executable, "-m", "outro.app"])
    with pytest.raises(launcher.LaunchError):
        launcher.running_pid(pidfile, "gravador")


def test_pid_ausente_nao_inspeciona_processos(tmp_path, monkeypatch):
    def unexpected(_pid):
        pytest.fail("nao deve consultar processos sem arquivo PID")

    monkeypatch.setattr(launcher, "process_command", unexpected)
    assert launcher.running_pid(tmp_path / "ausente.pid", "gravador") is None


def test_wait_ready_detecta_saida_precoce_sem_esperar_timeout(monkeypatch):
    monkeypatch.setattr(launcher, "_api_ready", lambda *_: False)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: pytest.fail("filho ja encerrou"))
    with pytest.raises(launcher.LaunchError):
        launcher.wait_ready("http://127.0.0.1:18765", child=SimpleNamespace(poll=lambda: 7), timeout=30)


def test_wait_ready_tem_timeout_limitado_sem_espera_real(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(launcher, "_api_ready", lambda *_: False)
    monkeypatch.setattr(launcher.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(launcher.time, "sleep", lambda duration: clock.__setitem__("now", clock["now"] + max(duration, 1)))
    with pytest.raises(launcher.LaunchError):
        launcher.wait_ready("http://127.0.0.1:18765", timeout=2)
    assert clock["now"] <= 4


def test_wait_ready_aceita_api_pronta_sem_espera(monkeypatch):
    monkeypatch.setattr(launcher, "_api_ready", lambda *_: True)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: pytest.fail("API ja pronta"))
    launcher.wait_ready("http://127.0.0.1:18765", timeout=2)


def test_pid_de_outra_instalacao_python_nao_e_aceito(tmp_path, monkeypatch):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        str(tmp_path / "outra-instalacao" / "python.exe"), "-m", "app.main"])
    with pytest.raises(launcher.LaunchError):
        launcher.running_pid(pidfile, "gravador")


def test_verificar_nao_inicia_servicos_navegador_ou_logs(tmp_path, monkeypatch):
    from app import config as config_mod

    cfg = SimpleNamespace(port=18765)
    monkeypatch.setenv("PREGACAO_HOME", str(tmp_path))
    monkeypatch.setattr(config_mod, "Config", lambda home: cfg)
    monkeypatch.setattr(config_mod, "load_env", lambda _: {})
    checked = []

    def diagnostic(config, env):
        checked.append((config, env))
        return 0

    def unexpected(*_args, **_kwargs):
        pytest.fail("--verificar nao pode iniciar servicos ou navegador")

    monkeypatch.setattr(launcher, "diagnostic", diagnostic)
    monkeypatch.setattr(launcher, "launch", unexpected)
    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    monkeypatch.setattr(launcher.webbrowser, "open", unexpected)
    monkeypatch.setattr(launcher, "_launch_lock", unexpected)
    monkeypatch.setattr(launcher, "_file_logger", unexpected)
    assert launcher.main(["--verificar"]) == 0
    assert len(checked) == 1
    assert checked[0][0] is cfg
    assert Path(checked[0][1]["PREGACAO_HOME"]) == tmp_path


def test_main_falha_mqtt_mantem_gravador_e_informa_resultado(tmp_path, monkeypatch, capsys):
    from app import config as config_mod

    monkeypatch.setenv("PREGACAO_HOME", str(tmp_path))
    monkeypatch.setenv("PREGACAO_REMOTE_HOST", "broker.invalid")
    monkeypatch.setenv("PREGACAO_REMOTE_ENABLED", "auto")
    monkeypatch.setattr(config_mod, "Config", lambda home: SimpleNamespace(port=18765))
    monkeypatch.setattr(config_mod, "load_env", lambda _: {})
    monkeypatch.setattr(launcher, "_launch_lock", lambda _: nullcontext())
    logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None,
                             error=lambda *a: None)
    monkeypatch.setattr(launcher, "_file_logger", lambda *_: logger)
    launched = []

    def launch(component, *_args, **_kwargs):
        launched.append(component)
        if component == "agente":
            raise launcher.LaunchError("MQTT indisponivel")
        return True

    def unexpected(*_args, **_kwargs):
        pytest.fail("nenhum processo ou navegador real deve ser iniciado")

    monkeypatch.setattr(launcher, "launch", launch)
    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    monkeypatch.setattr(launcher.webbrowser, "open", unexpected)
    assert launcher.main(["--sem-navegador"]) == 1
    assert launched == ["gravador", "agente"]
    output = capsys.readouterr().out
    assert "MQTT indisponivel" in output
    assert "continua funcionando" in output
    assert "http://127.0.0.1:18765" in output


@pytest.fixture
def main_context(tmp_path, monkeypatch):
    from app import config as config_mod

    home = tmp_path / "Home configurado"
    cfg = SimpleNamespace(port=18765, host="192.0.2.11")
    monkeypatch.setenv("PREGACAO_HOME", str(home))
    monkeypatch.setenv("PATH", "path-original-sintetico")
    monkeypatch.delenv("PREGACAO_API_BASE", raising=False)
    monkeypatch.delenv("PREGACAO_REMOTE_HOST", raising=False)
    monkeypatch.setenv("PREGACAO_REMOTE_ENABLED", "auto")
    config_homes = []
    env_paths = []
    launches = []

    def config(selected_home):
        config_homes.append(selected_home)
        return cfg

    def launch(component, root, selected_home, env, url):
        launches.append((component, selected_home, env, url))
        return True

    def unexpected(*_args, **_kwargs):
        pytest.fail("nenhuma API ou processo real deve ser usado neste teste")

    logger = SimpleNamespace(info=lambda *a: None, warning=lambda *a: None,
                             error=lambda *a: None)
    monkeypatch.setattr(config_mod, "Config", config)
    monkeypatch.setattr(config_mod, "load_env", lambda path: env_paths.append(path))
    monkeypatch.setattr(launcher, "_file_logger", lambda *_: logger)
    monkeypatch.setattr(launcher, "_launch_lock", lambda _: nullcontext())
    monkeypatch.setattr(launcher, "launch", launch)
    monkeypatch.setattr(launcher, "wait_ready", unexpected)
    monkeypatch.setattr(launcher, "_api_ready", unexpected)
    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    monkeypatch.setattr(launcher.webbrowser, "open", unexpected)
    return SimpleNamespace(home=home, cfg=cfg, config_homes=config_homes,
                           env_paths=env_paths, launches=launches)


def test_main_preserva_home_explicito_e_ambiente_do_venv(main_context):
    assert launcher.main(["--somente-gravador", "--sem-navegador"]) == 0
    assert main_context.config_homes == [main_context.home]
    assert main_context.env_paths == [main_context.home / ".env"]
    component, home, env, url = main_context.launches[0]
    assert component == "gravador"
    assert home == main_context.home
    assert Path(env["PREGACAO_HOME"]) == main_context.home
    assert env["PATH"].split(launcher.os.pathsep)[0] == str(Path(launcher.sys.executable).parent)
    assert env["PATH"].endswith("path-original-sintetico")
    assert env["VIRTUAL_ENV"] == launcher.sys.prefix
    assert launcher.os.environ["PATH"] == "path-original-sintetico"
    assert url == "http://192.0.2.11:18765"
    assert env["PREGACAO_API_BASE"] == url


def test_somente_agente_inicia_independente_da_api(main_context, monkeypatch):
    monkeypatch.setenv("PREGACAO_REMOTE_HOST", "broker.invalid")
    assert launcher.main(["--somente-agente"]) == 0
    assert [item[0] for item in main_context.launches] == ["agente"]


def test_url_lan_preserva_api_base_explicita(main_context, monkeypatch):
    override = "http://api-alternativa.invalid:19999"
    monkeypatch.setenv("PREGACAO_API_BASE", override)
    assert launcher.main(["--somente-gravador", "--sem-navegador"]) == 0
    assert main_context.launches[0][3] == "http://192.0.2.11:18765"
    assert main_context.launches[0][2]["PREGACAO_API_BASE"] == override


def test_erro_leitura_env_exibe_mensagem_neutra(main_context, monkeypatch, capsys):
    from app import config as config_mod

    def unreadable(_path):
        raise OSError("conteudo-sensivel-nao-deve-aparecer")

    monkeypatch.setattr(config_mod, "load_env", unreadable)
    assert launcher.main(["--sem-navegador"]) == 1
    assert main_context.launches == []
    output = capsys.readouterr()
    assert "[ERRO]" in output.out
    assert "configuracao local" in output.out
    assert "conteudo-sensivel" not in output.out + output.err
    assert "Traceback" not in output.out + output.err


def test_diagnostico_real_nao_cria_banco_arquivos_ou_processos(tmp_path, monkeypatch, capsys):
    import sqlite3
    from app import config as config_mod

    monkeypatch.setenv("PREGACAO_HOME", str(tmp_path))
    monkeypatch.delenv("PREGACAO_REMOTE_HOST", raising=False)
    monkeypatch.setattr(config_mod, "load_env", lambda _: {})
    imported = []

    def import_dependency(name):
        assert not name.startswith("app."), "diagnostico nao deve importar servicos"
        imported.append(name)
        if name.startswith(("googleapiclient", "google_auth")):
            raise ModuleNotFoundError(name)
        return SimpleNamespace()

    def unexpected(*_args, **_kwargs):
        pytest.fail("diagnostico nao pode criar banco, processo ou arquivo de log")

    monkeypatch.setattr(launcher.importlib, "import_module", import_dependency)
    monkeypatch.setattr(launcher.shutil, "which", lambda *a, **k: "ferramenta-sintetica.exe")
    monkeypatch.setattr(sqlite3, "connect", unexpected)
    monkeypatch.setattr(launcher, "launch", unexpected)
    monkeypatch.setattr(launcher, "_run_service", unexpected)
    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    monkeypatch.setattr(launcher.webbrowser, "open", unexpected)
    monkeypatch.setattr(launcher, "_file_logger", unexpected)
    monkeypatch.setattr(launcher, "_launch_lock", unexpected)
    before = sorted(tmp_path.rglob("*"))
    assert launcher.main(["--verificar"]) == 0
    assert sorted(tmp_path.rglob("*")) == before
    assert {"flask", "werkzeug", "waitress"}.issubset(imported)
    assert "googleapiclient.discovery" in imported
    output = capsys.readouterr().out
    assert "[AVISO] bibliotecas do Google Drive" in output
    assert "Nenhum servico, captura ou envio foi iniciado" in output
