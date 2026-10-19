"""Pipeline incorporado: caminhos e contrato sem CLI, login ou envio reais."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "sermon-pipeline"


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    data = tmp_path / "Dados com espacos e acentos" / "pipeline"
    monkeypatch.setenv("PREGACAO_PIPELINE_HOME", str(data))
    monkeypatch.setenv("PREGACAO_NODE", str(tmp_path / "runtime" / "node.exe"))
    spec = importlib.util.spec_from_file_location("pipeline_vendor_test", VENDOR / "pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def blocked(*args, **kwargs):
        pytest.fail("Subprocessos de pipeline/rede nao sao permitidos neste teste")

    monkeypatch.setattr(module.subprocess, "run", blocked)
    return module


def test_import_e_config_padrao_nao_criam_dados_nem_credenciais(pipeline):
    assert not pipeline.DATA_ROOT.exists()
    cfg = pipeline.load_config()
    assert cfg["whatsapp_number"] == ""
    assert cfg["report_language"] == "pt_BR"
    assert cfg["source_wait_timeout"] > 0 and cfg["report_timeout"] > 0
    assert not pipeline.DATA_ROOT.exists()
    assert pipeline.PROMPT_FILE == VENDOR / "prompt.txt"
    assert pipeline.CONFIG_FILE == pipeline.DATA_ROOT / "config.json"
    assert pipeline.OUTPUT == pipeline.DATA_ROOT / "output"
    assert pipeline.NLM == [sys.executable, "-m", "notebooklm"]


def test_config_local_completa_defaults_sem_reescrever_arquivo(pipeline):
    pipeline.DATA_ROOT.mkdir(parents=True)
    original = '{"report_timeout": 42, "whatsapp_number": ""}'
    pipeline.CONFIG_FILE.write_text(original, encoding="utf-8")
    cfg = pipeline.load_config()
    assert cfg["report_timeout"] == 42
    assert cfg["source_wait_timeout"] > 0
    assert pipeline.CONFIG_FILE.read_text(encoding="utf-8") == original


def test_config_local_recusa_array(pipeline):
    pipeline.DATA_ROOT.mkdir(parents=True)
    pipeline.CONFIG_FILE.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="objeto JSON"):
        pipeline.load_config()


def test_exec_herda_runtime_perfil_browser_e_certificados_sem_consultar_pc(pipeline, monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_HOME", str(pipeline.DATA_ROOT / "nlm"))
    monkeypatch.setenv("NOTEBOOKLM_PROFILE", "perfil-de-teste")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(pipeline.DATA_ROOT / "browsers"))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "certificado-sintetico.pem")
    monkeypatch.setenv("PATH", "caminho-controlado-de-teste")
    seen = []

    def fake_run(command, **options):
        seen.append((command, options))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    pipeline._exec([*pipeline.NLM, "auth", "check", "--test", "--passive"], 60)
    command, options = seen[0]
    assert command[:3] == [sys.executable, "-m", "notebooklm"]
    assert options["cwd"] == VENDOR
    assert options["env"]["PATH"] == "caminho-controlado-de-teste"
    assert options["env"]["PREGACAO_PIPELINE_HOME"] == str(pipeline.DATA_ROOT)
    for key in ("NOTEBOOKLM_HOME", "NOTEBOOKLM_PROFILE", "PLAYWRIGHT_BROWSERS_PATH", "REQUESTS_CA_BUNDLE"):
        assert options["env"][key] == os.environ[key]
    assert options["creationflags"] == (subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


def test_notebooklm_usa_mesmo_python_preserva_prompt_e_marcos(pipeline, monkeypatch, tmp_path, capsys):
    audio = tmp_path / "Pregacao com acento.mp3"
    audio.write_bytes(b"audio sintetico")
    commands = []

    def fake_run(command, **options):
        command = [str(part) for part in command]
        commands.append(command)
        args = command[3:]
        if args[0] == "create":
            output = '{"notebook_id":"nb-sintetico"}'
        elif args[:2] == ["source", "add"]:
            output = '{"source_id":"fonte-sintetica"}'
        else:
            output = ""
        if args[:2] == ["download", "report"]:
            Path(args[2]).write_text("# Estudo simulado", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(pipeline, "run", fake_run)
    result = pipeline.step_notebooklm(pipeline.load_config(), audio, "Titulo de teste")
    assert result.parent == pipeline.DATA_ROOT / "output"
    assert result.read_text(encoding="utf-8") == "# Estudo simulado"
    assert len(commands) == 5
    assert all(command[:3] == [sys.executable, "-m", "notebooklm"] for command in commands)
    generation = next(command for command in commands if "generate" in command)
    assert generation[generation.index("--prompt-file") + 1] == str(VENDOR / "prompt.txt")
    assert "nb-sintetico" in generation
    output = capsys.readouterr().out
    assert all(f"=== {step}." in output for step in (3, 4, 5, 6))


def test_refresh_do_modulo_notebooklm_mantem_retry_unico(pipeline, monkeypatch):
    calls = []
    responses = iter([
        SimpleNamespace(returncode=1, stdout="AUTH_ERROR", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="resultado", stderr=""),
    ])

    def execute(command, timeout=None):
        calls.append(command)
        return next(responses)

    monkeypatch.setattr(pipeline, "_exec", execute)
    command = [*pipeline.NLM, "create", "sintetico", "--json"]
    result = pipeline.run(command)
    assert result.returncode == 0
    assert calls == [command, [*pipeline.NLM, "auth", "refresh", "--allow-headless", "--verify"], command]
    assert not pipeline._is_notebooklm([pipeline.NODE, "send.js"])


def test_pdf_usa_python_corrente_e_converte_markdown_com_bibliotecas_simuladas(pipeline, monkeypatch, tmp_path):
    markdown_path = tmp_path / "Estudo com acentos.md"
    markdown_path.write_text("# Audio e estudo", encoding="utf-8")
    seen = []
    markdown = ModuleType("markdown")
    markdown.markdown = lambda source, extensions: "<h1>Audio e estudo</h1>"
    xhtml2pdf = ModuleType("xhtml2pdf")

    def create_pdf(html, dest, encoding):
        assert "<h1>Audio e estudo</h1>" in html
        assert encoding == "utf-8"
        dest.write(b"%PDF-simulado")
        return SimpleNamespace(err=0)

    xhtml2pdf.pisa = SimpleNamespace(CreatePDF=create_pdf)
    monkeypatch.setitem(sys.modules, "markdown", markdown)
    monkeypatch.setitem(sys.modules, "xhtml2pdf", xhtml2pdf)

    def run_conversion(command, **kwargs):
        seen.append(command)
        with monkeypatch.context() as context:
            context.setattr(sys, "argv", ["-c", str(command[3]), str(command[4])])
            exec(compile(command[2], "<pdf-simulado>", "exec"), {})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pipeline, "run", run_conversion)
    pdf = pipeline.step_md_to_pdf(markdown_path)
    assert seen[0][0:2] == [sys.executable, "-c"]
    assert pdf == markdown_path.with_suffix(".pdf")
    assert pdf.read_bytes() == b"%PDF-simulado"


def test_pdf_sem_arquivo_nao_e_considerado_concluido(pipeline, monkeypatch, tmp_path):
    source = tmp_path / "ausente.md"
    source.write_text("# sintetico", encoding="utf-8")
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    with pytest.raises(SystemExit, match="conversao PDF falhou"):
        pipeline.step_md_to_pdf(source)


def test_whatsapp_resolve_node_privado_e_pula_sem_destinatario(pipeline, monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(pipeline, "run", lambda cmd, **kw: calls.append((cmd, kw)))
    pdf = tmp_path / "estudo.pdf"
    pipeline.step_whatsapp(pipeline.load_config(), pdf, "Estudo", None, False)
    assert calls == []
    assert "=== 8. Envio por WhatsApp pulado" in capsys.readouterr().out
    pipeline.step_whatsapp(pipeline.load_config(), pdf, "Estudo", "5500000000000", False)
    assert calls[0][0][0] == os.environ["PREGACAO_NODE"]
    assert calls[0][0][1] == VENDOR / "whatsapp" / "send.js"
    assert calls[0][1] == {"timeout": 180}


def test_cli_integrado_preserva_skip_drive_e_ordem(pipeline, monkeypatch, tmp_path, capsys):
    audio = tmp_path / "audio_do_teste.mp3"
    audio.write_bytes(b"audio sintetico")
    md, pdf = tmp_path / "estudo.md", tmp_path / "estudo.pdf"
    calls = []
    monkeypatch.setattr(pipeline, "step_upload_to_drive", lambda *a: pytest.fail("--skip-drive foi ignorado"))
    monkeypatch.setattr(pipeline, "step_notebooklm", lambda cfg, path, title: calls.append(("nlm", path, title)) or md)
    monkeypatch.setattr(pipeline, "step_md_to_pdf", lambda path: calls.append(("pdf", path)) or pdf)
    monkeypatch.setattr(pipeline, "step_whatsapp", lambda cfg, path, title, to, skip: calls.append(("whatsapp", path, to, skip)))
    monkeypatch.setattr(sys, "argv", ["pipeline.py", str(audio), "--skip-drive", "--to", "5500000000000"])
    pipeline.main()
    assert calls == [("nlm", audio, "audio do teste"), ("pdf", md), ("whatsapp", pdf, "5500000000000", False)]
    assert "=== CONCLUIDO" in capsys.readouterr().out


def test_manifests_node_estao_coerentes_e_usam_so_resolved_publicos():
    package = json.loads((VENDOR / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((VENDOR / "package-lock.json").read_text(encoding="utf-8"))
    assert package["private"] is True
    assert package["dependencies"] == lock["packages"][""]["dependencies"]
    for name, version in package["dependencies"].items():
        assert version == lock["packages"]["node_modules/" + name]["version"]
    for entry in lock["packages"].values():
        resolved = entry.get("resolved", "")
        assert not resolved or resolved.startswith(("https://registry.npmjs.org/", "https://registry.yarnpkg.com/", "https://github.com/", "git+https://github.com/"))


@pytest.mark.skipif(not shutil.which("node"), reason="Node nao disponivel para o teste isolado do sender")
def test_sender_guarda_auth_no_home_do_pipeline_sem_conectar(tmp_path):
    script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const home = process.argv[2];
const observations = [];
const baileys = {
  useMultiFileAuthState: async directory => {
    observations.push({kind: 'auth', directory});
    return {state: {}, saveCreds: () => {}};
  },
  makeWASocket: () => ({ev: {on: () => {}}}),
  Browsers: {ubuntu: () => ['synthetic']},
  DisconnectReason: {loggedOut: 401},
};
const fakeRequire = name => {
  if (name === 'path') return path;
  if (name === 'fs') return {mkdirSync: directory => observations.push({kind: 'mkdir', directory})};
  if (name === 'baileys') return baileys;
  if (name === 'qrcode-terminal') return {};
  throw new Error('Dependencia real bloqueada: ' + name);
};
vm.runInNewContext(source, {
  require: fakeRequire,
  __dirname: path.dirname(process.argv[1]),
  process: {argv: ['node', 'send.js', '--login'], env: {PREGACAO_PIPELINE_HOME: home}, exit: () => {throw new Error('exit inesperado');}},
  console: {log: () => {}, error: message => {throw new Error(message);}},
  setTimeout: () => {throw new Error('timer de conexao inesperado');},
});
setImmediate(() => console.log(JSON.stringify(observations)));
"""
    data = tmp_path / "dados isolados"
    result = subprocess.run([shutil.which("node"), "-e", script, str(VENDOR / "whatsapp" / "send.js"), str(data)],
                            capture_output=True, text=True, timeout=10, check=True)
    calls = json.loads(result.stdout)
    assert calls == [{"kind": "mkdir", "directory": str(data / "whatsapp")},
                     {"kind": "auth", "directory": str(data / "whatsapp" / "auth")}]
    assert not data.exists()


def test_prompt_preservado_conforme_snapshot_publico():
    source = json.loads((VENDOR / "SOURCE.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((VENDOR / "prompt.txt").read_bytes()).hexdigest()
    assert digest == source["source_snapshot_sha256"]["prompt.txt"]
    assert source["notebooklm_distribution"] == "notebooklm-py"
