"""Inicializacao Windows isolada: nenhum servidor, MQTT ou captura reais."""
from __future__ import annotations

import copy
from contextlib import nullcontext
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import launcher


REAL_RUNNING_PID = launcher.running_pid


@pytest.fixture
def context(tmp_path, monkeypatch):
    root = tmp_path / "Projeto com espaços & acentos"
    home = tmp_path / "Dados preservados ç ã"
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
                           "--service", component, "--service-root", str(context.root),
                           "--service-home", str(context.home)]
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
def test_pid_legado_do_modulo_nao_e_reutilizado_sem_confirmar_instalacao(tmp_path, monkeypatch, component, module):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [launcher.sys.executable, "-m", module])
    with pytest.raises(launcher.LaunchError, match="servico antigo sem identidade"):
        launcher.running_pid(pidfile, component)


@pytest.mark.parametrize("component", ["gravador", "agente"])
def test_pid_do_servico_do_launcher_e_reconhecido(tmp_path, monkeypatch, component):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        launcher.sys.executable, "-B", "-m", "app.launcher", "--service", component,
        "--service-root", str(tmp_path), "--service-home", str(tmp_path)])
    assert launcher.running_pid(pidfile, component, tmp_path, tmp_path) == 12345


@pytest.mark.skipif(launcher.os.name != "nt", reason="executavel sem console do Windows")
@pytest.mark.parametrize("component", ["gravador", "agente"])
def test_pid_do_pythonw_e_reconhecido_pelo_python_console(tmp_path, monkeypatch, component):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    base = Path(getattr(launcher.sys, "_base_executable", None) or launcher.sys.executable)
    pythonw = base.with_name("pythonw.exe")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        str(pythonw), "-B", "-m", "app.launcher", "--service", component,
        "--service-root", str(tmp_path), "--service-home", str(tmp_path)])
    assert launcher.running_pid(pidfile, component, tmp_path, tmp_path) == 12345


@pytest.mark.parametrize("component", ["gravador", "agente"])
def test_pid_legado_do_launcher_nao_e_reutilizado(tmp_path, monkeypatch, component):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        launcher.sys.executable, "-B", "-m", "app.launcher", "--service", component])
    with pytest.raises(launcher.LaunchError, match="servico antigo sem identidade"):
        launcher.running_pid(pidfile, component, tmp_path, tmp_path)


@pytest.mark.parametrize("component", ["gravador", "agente"])
@pytest.mark.parametrize("different_root,different_home", [(True, False), (False, True), (True, True)])
def test_pid_copiado_de_outra_instalacao_com_mesmo_python_nao_inicia_duplicata(
        context, monkeypatch, component, different_root, different_home):
    pidfile = context.home / "logs" / launcher.PID_FILES[component]
    pidfile.write_text("12345", encoding="utf-8")
    other_root = context.root.parent / "Outra cópia" if different_root else context.root
    other_home = context.home.parent / "Outros dados" if different_home else context.home
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        launcher.sys.executable, "-B", "-m", "app.launcher", "--service", component,
        "--service-root", str(other_root), "--service-home", str(other_home)])
    # O fixture substitui a consulta; restaura apenas a funcao real, sem tocar nos filhos simulados.
    monkeypatch.setattr(launcher, "running_pid", REAL_RUNNING_PID)
    with pytest.raises(launcher.LaunchError, match="outra instalacao ou pasta de dados"):
        launcher.launch(component, context.root, context.home, context.env, context.url, 2)
    assert context.spawned == []
    assert context.ready == []
    assert context.agents == []
    assert pidfile.read_text(encoding="utf-8") == "12345"


@pytest.mark.parametrize("component", ["gravador", "agente"])
def test_pid_desta_instalacao_e_home_e_reutilizado_sem_duplicata(context, monkeypatch, component):
    pidfile = context.home / "logs" / launcher.PID_FILES[component]
    pidfile.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(launcher, "process_command", lambda _: [
        launcher.sys.executable, "-B", "-m", "app.launcher", "--service", component,
        "--service-root", str(context.root), "--service-home", str(context.home)])
    monkeypatch.setattr(launcher, "running_pid", REAL_RUNNING_PID)
    assert launcher.launch(component, context.root, context.home, context.env, context.url, 2) is False
    assert context.spawned == []


@pytest.mark.parametrize("marker", ["--service-root", "--service-home"])
def test_marcador_relativo_nao_comprova_instalacao(tmp_path, monkeypatch, marker):
    pidfile = tmp_path / "processo.pid"
    pidfile.write_text("12345", encoding="utf-8")
    command = [launcher.sys.executable, "-B", "-m", "app.launcher", "--service", "gravador",
               "--service-root", str(tmp_path), "--service-home", str(tmp_path)]
    command[command.index(marker) + 1] = "."
    monkeypatch.setattr(launcher, "process_command", lambda _: command)
    with pytest.raises(launcher.LaunchError):
        launcher.running_pid(pidfile, "gravador", tmp_path, tmp_path)


@pytest.mark.skipif(launcher.os.name != "nt", reason="parser nativo de linha de comando Windows")
def test_identidade_windows_preserva_espacos_acentos_e_e_comercial(tmp_path, monkeypatch):
    root = tmp_path / "Instalação com espaços & acentos"
    home = tmp_path / "Dados do João"
    command = [launcher.sys.executable, "-B", "-m", "app.launcher", "--service", "gravador",
               "--service-root", str(root), "--service-home", str(home)]
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: SimpleNamespace(
        stdout=launcher.json.dumps(subprocess.list2cmdline(command), ensure_ascii=False)))
    assert launcher.process_command(12345) == command


def test_servico_confere_marcadores_antes_de_entregar_ao_modulo(tmp_path, monkeypatch):
    from app import bundled_runtime

    root = Path(launcher.__file__).resolve().parent.parent
    home = tmp_path / "Dados com acentos ç e espaços"
    monkeypatch.setenv("PREGACAO_HOME", str(home))
    monkeypatch.setattr(launcher.sys, "argv", ["argumentos-do-teste"])
    monkeypatch.setattr(bundled_runtime, "prepare_environment", lambda **_: None)
    services = []
    monkeypatch.setattr(launcher, "_run_service", lambda component, selected_home:
                        services.append((component, selected_home, list(launcher.sys.argv))) or 7)
    assert launcher.main(["--service", "gravador", "--service-root", str(root),
                          "--service-home", str(home)]) == 7
    assert services == [("gravador", home, ["app.main"])]
    assert not home.exists()


@pytest.mark.parametrize("invalid", ["missing", "root", "home", "relative"])
def test_servico_com_marcadores_incompativeis_nao_inicia(tmp_path, monkeypatch, capsys, invalid):
    from app import bundled_runtime

    root = Path(launcher.__file__).resolve().parent.parent
    home = tmp_path / "Dados atuais"
    monkeypatch.setenv("PREGACAO_HOME", str(home))
    monkeypatch.setattr(bundled_runtime, "prepare_environment", lambda **_: None)

    def unexpected(*_args, **_kwargs):
        pytest.fail("identidade divergente nao pode executar um servico")

    monkeypatch.setattr(launcher, "_run_service", unexpected)
    arguments = ["--service", "gravador"]
    if invalid != "missing":
        arguments += ["--service-root", str(tmp_path / "outra") if invalid == "root" else str(root),
                      "--service-home", str(tmp_path / "outros") if invalid == "home"
                      else "." if invalid == "relative" else str(home)]
    assert launcher.main(arguments) == 1
    assert "[ERRO]" in capsys.readouterr().out
    assert not home.exists()


def test_pid_nativo_em_copia_sintetica_reutiliza_apenas_mesma_instalacao(tmp_path, monkeypatch):
    """Processo de teste so grava PID temporario; nao importa o servidor ou filas."""
    from app import bundled_runtime

    root = tmp_path / "Cópia sintética & espaços"
    home = tmp_path / "Dados sintéticos ç"
    app = root / "app"
    app.mkdir(parents=True)
    (app / "__init__.py").write_text("", encoding="utf-8")
    launcher.shutil.copyfile(launcher.__file__, app / "launcher.py")
    launcher.shutil.copyfile(bundled_runtime.__file__, app / "bundled_runtime.py")
    (app / "main.py").write_text(
        "import os\nfrom pathlib import Path\nimport time\n"
        "pidfile = Path(os.environ['PREGACAO_HOME']) / 'logs' / 'servidor.pid'\n"
        "pidfile.parent.mkdir(parents=True, exist_ok=True)\n"
        "pidfile.write_text(str(os.getpid()), encoding='utf-8')\n"
        "deadline = time.monotonic() + 45\n"
        "while not pidfile.with_name('encerrar-teste').exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.05)\n", encoding="utf-8")
    env = dict(launcher.os.environ, PREGACAO_HOME=str(home), PYTHONPATH="")
    pidfile = home / "logs" / "servidor.pid"
    # O redirector de venv no Windows cria outro PID para o Python base.
    python = getattr(launcher.sys, "_base_executable", None) or launcher.sys.executable
    command = [python, "-B", "-m", "app.launcher", "--service", "gravador",
               "--service-root", str(root), "--service-home", str(home)]
    child = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=launcher._creationflags())
    try:
        deadline = launcher.time.monotonic() + 10
        while not pidfile.exists() and child.poll() is None and launcher.time.monotonic() < deadline:
            launcher.time.sleep(0.05)
        assert pidfile.read_text(encoding="utf-8") == str(child.pid)

        def unexpected(*_args, **_kwargs):
            pytest.fail("PID validado nao pode chegar a criacao de outro processo")

        monkeypatch.setattr(launcher, "dependency_check", unexpected)
        ready = []
        monkeypatch.setattr(launcher, "wait_ready", lambda *a, **k: ready.append((a, k)))
        for _ in range(2):
            assert launcher.launch("gravador", root, home, env, "http://127.0.0.1:18765", 2) is False
        assert len(ready) == 2
        with pytest.raises(launcher.LaunchError, match="outra instalacao ou pasta de dados"):
            launcher.launch("gravador", tmp_path / "Outra cópia", home, env,
                            "http://127.0.0.1:18765", 2)
        assert child.poll() is None
        assert pidfile.read_text(encoding="utf-8") == str(child.pid)
    finally:
        home.mkdir(parents=True, exist_ok=True)
        (home / "logs").mkdir(exist_ok=True)
        pidfile.with_name("encerrar-teste").touch()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=10)


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

    cfg = SimpleNamespace(port=18765, get=lambda _key, default=None: default)
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
    monkeypatch.setattr(config_mod, "Config", lambda home: SimpleNamespace(
        port=18765, get=lambda _key, default=None: default))
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
    cfg = SimpleNamespace(port=18765, host="192.0.2.11", get=lambda _key, default=None: default)
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
