"""Pacote Windows em pastas temporarias; nenhum servico ou conta real."""
from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import bundled_runtime, launcher


@pytest.fixture
def package(tmp_path, monkeypatch):
    root = tmp_path / "Pacote com espa\u00e7os e a\u00e7\u00e3o"
    for child in ("gravador/config", "pipeline", "runtime/python", "runtime/node",
                  "runtime/ffmpeg/bin", "runtime/browsers"):
        (root / child).mkdir(parents=True)
    (root / "package-manifest.json").write_text(json.dumps({
        "schema_version": 1, "name": "PregacaoRecorder", "version": "teste",
    }), encoding="utf-8")
    monkeypatch.setattr(bundled_runtime.os, "environ", {"PATH": "path-sintetico"})
    monkeypatch.setattr(bundled_runtime, "__file__", str(root / "gravador/app/bundled_runtime.py"))
    monkeypatch.setattr(launcher, "__file__", str(root / "gravador/app/launcher.py"))
    return root


def test_manifest_sem_layout_nao_transforma_desenvolvimento_em_pacote(tmp_path, monkeypatch):
    recorder = tmp_path / "gravador"
    recorder.mkdir()
    (tmp_path / "package-manifest.json").write_text('{"schema_version":1,"name":"PregacaoRecorder"}')
    original = {"PATH": "dev-original", "PREGACAO_HOME": "dados-explicitos",
                "VIRTUAL_ENV": "venv-original", "PREGACAO_BUNDLED_ROOT": str(tmp_path)}
    monkeypatch.setattr(bundled_runtime.os, "environ", original.copy())
    assert bundled_runtime.prepare_environment(recorder_root=recorder, create_config=True) is None
    assert dict(bundled_runtime.os.environ) == original
    assert not (recorder / "config").exists()


@pytest.mark.parametrize("contents", ["invalido", "[]", "{}",
    '{"schema_version":2,"name":"PregacaoRecorder"}',
    '{"schema_version":1,"name":"outro-produto"}'])
def test_marker_invalido_nao_habilita_runtime(package, contents):
    (package / "package-manifest.json").write_text(contents)
    assert bundled_runtime.detect_package() is None
    assert bundled_runtime.is_bundled() is False


def test_pacote_validado_prepara_ferramentas_sem_criar_dados(package):
    env = bundled_runtime.os.environ
    env["PREGACAO_HOME"] = "outro-home-herdado"
    env["VIRTUAL_ENV"] = "venv-do-desenvolvedor"
    before = sorted(package.rglob("*"))
    assert bundled_runtime.prepare_environment() == package
    assert bundled_runtime.is_bundled() is True
    assert env["PREGACAO_HOME"] == str(package / "gravador")
    assert env["PREGACAO_BUNDLED_ROOT"] == str(package)
    assert env["PREGACAO_NODE"] == str(package / "runtime/node/node.exe")
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(package / "runtime/browsers")
    assert env["NOTEBOOKLM_HOME"] == str(package / "gravador/data/notebooklm")
    assert env["PREGACAO_PIPELINE_HOME"] == str(package / "pipeline")
    assert "VIRTUAL_ENV" not in env
    parts = env["PATH"].split(bundled_runtime.os.pathsep)
    assert parts[:4] == [str(package / child) for child in
                         ("runtime/python", "runtime/python/Scripts", "runtime/node", "runtime/ffmpeg/bin")]
    assert parts[-1] == "path-sintetico"
    assert sorted(package.rglob("*")) == before
    original_path = env["PATH"]
    bundled_runtime.prepare_environment()
    assert env["PATH"] == original_path


def test_perfil_explicito_e_preservado_e_primeira_config_nao_contem_segredos(package):
    env = bundled_runtime.os.environ
    env["NOTEBOOKLM_HOME"] = str(package / "perfil-escolhido")
    env["NOTEBOOKLM_PROFILE"] = "perfil-local"
    env["PREGACAO_PIPELINE_HOME"] = str(package / "dados-do-pipeline")
    bundled_runtime.prepare_environment(create_config=True)
    assert env["NOTEBOOKLM_HOME"] == str(package / "perfil-escolhido")
    assert env["NOTEBOOKLM_PROFILE"] == "perfil-local"
    assert env["PREGACAO_PIPELINE_HOME"] == str(package / "dados-do-pipeline")
    settings = json.loads((package / "gravador/config/config.json").read_text(encoding="utf-8"))
    assert settings == {"estudos": {"python": bundled_runtime.sys.executable,
                                    "pasta": str(package / "pipeline")}}
    assert not (package / "gravador/.env").exists()
    assert not list((package / "gravador/config").glob("initial-config-*"))


def test_configuracao_existente_e_preservada_sem_reescrita(package):
    target = package / "gravador/config/config.json"
    original = '{ "estudos": {"pasta": "preferencia-existente"}, "custom": true }'
    target.write_text(original, encoding="utf-8")
    modified = target.stat().st_mtime_ns
    bundled_runtime.prepare_environment(create_config=True)
    assert target.read_text(encoding="utf-8") == original
    assert target.stat().st_mtime_ns == modified


def test_criacao_concorrente_preserva_config_completa_do_outro_iniciador(package, monkeypatch):
    target = package / "gravador/config/config.json"
    original = '{"preferencia":"abertura-concorrente"}'

    def concurrent_publish(_source, destination):
        assert Path(destination) == target
        target.write_text(original, encoding="utf-8")
        raise FileExistsError("outro iniciador publicou primeiro")

    monkeypatch.setattr(bundled_runtime.os, "link", concurrent_publish)
    bundled_runtime.prepare_environment(create_config=True)
    assert target.read_text(encoding="utf-8") == original
    assert not list(target.parent.glob("initial-config-*"))


def test_launcher_verificar_usa_caminhos_iniciais_sem_criar_arquivos(package, monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod, "load_env", lambda path: {})
    captured = []

    def diagnostic(cfg, env):
        captured.append((cfg.get("estudos.pasta"), cfg.get("estudos.python"), env))
        return 0

    def unexpected(*args, **kwargs):
        pytest.fail("diagnostico nao pode iniciar componentes")

    monkeypatch.setattr(launcher, "diagnostic", diagnostic)
    monkeypatch.setattr(launcher, "_file_logger", unexpected)
    monkeypatch.setattr(launcher, "_launch_lock", unexpected)
    monkeypatch.setattr(launcher, "launch", unexpected)
    before = sorted(package.rglob("*"))
    assert launcher.main(["--verificar"]) == 0
    assert sorted(package.rglob("*")) == before
    assert captured[0][:2] == (str(package / "pipeline"), bundled_runtime.sys.executable)
    assert captured[0][2]["PREGACAO_HOME"] == str(package / "gravador")


def test_launcher_prepara_home_e_config_antes_de_importar_servico(package, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher.sys, "argv", list(launcher.sys.argv))

    def service(component, home):
        assert component == "gravador"
        assert home == package / "gravador"
        assert bundled_runtime.os.environ["PREGACAO_NODE"].endswith("node.exe")
        assert (home / "config/config.json").is_file()
        calls.append(component)
        return 0

    monkeypatch.setattr(launcher, "_run_service", service)
    assert launcher.main(["--service", "gravador"]) == 0
    assert calls == ["gravador"]


def test_cli_recebe_ambiente_do_pacote_sem_iniciar_servicos(package, monkeypatch):
    calls = []
    monkeypatch.setattr(launcher.sys, "argv", list(launcher.sys.argv))

    def run_module(module, **kwargs):
        assert module == "app.cli"
        assert launcher.sys.argv == ["pregacao", "logs", "-n", "12"]
        assert bundled_runtime.os.environ["PREGACAO_HOME"] == str(package / "gravador")
        assert (package / "gravador/config/config.json").is_file()
        calls.append(module)
        raise SystemExit(7)

    monkeypatch.setattr(launcher.runpy, "run_module", run_module)
    assert launcher.main(["--cli", "logs", "-n", "12"]) == 7
    assert calls == ["app.cli"]


def test_launcher_propaga_ferramentas_privadas_aos_filhos(package, monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod, "load_env", lambda path: {})
    monkeypatch.setattr(config_mod, "Config", lambda home: SimpleNamespace(port=18765, host="127.0.0.1"))
    monkeypatch.setattr(launcher, "_launch_lock", lambda home: nullcontext())
    logger = SimpleNamespace(info=lambda *args: None)
    monkeypatch.setattr(launcher, "_file_logger", lambda *args: logger)
    spawned = []
    monkeypatch.setattr(launcher, "launch", lambda component, root, home, env, url:
                        spawned.append((component, home, env)) or True)
    assert launcher.main(["--somente-gravador", "--sem-navegador"]) == 0
    component, home, env = spawned[0]
    assert component == "gravador"
    assert home == package / "gravador"
    assert env["PREGACAO_NODE"] == str(package / "runtime/node/node.exe")
    assert env["PLAYWRIGHT_BROWSERS_PATH"] == str(package / "runtime/browsers")
    assert env["PATH"].split(bundled_runtime.os.pathsep)[0] == str(package / "runtime/python")
    assert "VIRTUAL_ENV" not in env
