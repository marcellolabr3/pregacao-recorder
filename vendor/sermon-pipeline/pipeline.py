#!/usr/bin/env python
"""sermon-pipeline — áudio da mesa -> Google Drive -> NotebookLM -> PDF -> WhatsApp.

Uso:
    python pipeline.py <arquivo-de-audio>
    python pipeline.py --drive <nome-do-arquivo-no-drive>
    python pipeline.py <arquivo> --to 5511999999999
    python pipeline.py <arquivo> --skip-whatsapp

Passos executados:
 1. (opcional) baixa o áudio do Google Drive
 2. envia o áudio para o Google Drive (rclone)
 3. cria um notebook no NotebookLM e adiciona o áudio como fonte
 4. gera o ESTUDO/DEVOCIONAL com o prompt de prompt.txt (artifact "report")
 5. baixa o relatorio em Markdown e converte para PDF
 6. envia o PDF por WhatsApp (Baileys)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Windows: saida em UTF-8 (a saida do notebooklm tem simbolos como ✓)
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("PREGACAO_PIPELINE_HOME") or ROOT).expanduser().resolve()
PYTHON = sys.executable
NLM = [PYTHON, "-m", "notebooklm"]
PROMPT_FILE = ROOT / "prompt.txt"
CONFIG_FILE = DATA_ROOT / "config.json"
CONFIG_TEMPLATE = ROOT / "config.example.json"
INBOX = DATA_ROOT / "audio"
OUTPUT = DATA_ROOT / "output"
WHATSAPP_SCRIPT = ROOT / "whatsapp" / "send.js"
NODE = os.environ.get("PREGACAO_NODE") or shutil.which("node") or "node"
RCLONE = shutil.which("rclone") or "rclone"


def log(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def _exec(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Executa um comando, ecoando a saida em tempo real."""
    print(f"$ {' '.join(str(c) for c in cmd)}", flush=True)
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=ROOT,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=build_env(),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr, flush=True)
    return proc


def _is_notebooklm(cmd: list[str]) -> bool:
    return bool(cmd) and (
        "notebooklm" in str(cmd[0]).lower()
        or [str(part) for part in cmd[1:3]] == ["-m", "notebooklm"]
    )


def _auth_failed(proc: subprocess.CompletedProcess) -> bool:
    text = (proc.stdout or "") + (proc.stderr or "")
    return "AUTH_ERROR" in text or "Authentication expired" in text or "re-authenticate" in text


def refresh_auth() -> bool:
    """Renova a sessao do NotebookLM sem exigir interacao (best effort)."""
    try:
        p = _exec([*NLM, "auth", "refresh", "--allow-headless", "--verify"], timeout=90)
        return p.returncode == 0
    except Exception:
        return False


def run(cmd: list[str], check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess:
    """Executa um comando.

    Se um comando do NotebookLM falhar porque a sessao do Google expirou, renova a
    sessao automaticamente e repete o comando uma unica vez. Ao falhar, traduz o
    erro de autenticidade para uma mensagem compreensivel.
    """
    proc = _exec(cmd, timeout)
    if proc.returncode != 0 and _is_notebooklm(cmd) and _auth_failed(proc):
        print("\n=== Sessao do NotebookLM expirada; renovando e repetindo...", flush=True)
        if refresh_auth():
            proc = _exec(cmd, timeout)
    if check and proc.returncode != 0:
        if _is_notebooklm(cmd) and _auth_failed(proc):
            raise SystemExit(
                "ERRO: sessao do Google/NotebookLM expirou e nao foi possivel renovar sozinho. "
                "Execute 'notebooklm login' uma vez para re-autenticar."
            )
        raise SystemExit(f"ERRO: comando falhou (exit {proc.returncode}): {' '.join(str(c) for c in cmd)}")
    return proc


def build_env() -> dict:
    """Herde runtimes, browser/profile e certificados configurados pelo launcher.

    Nao importar PATH do registro ou certificados da maquina de desenvolvimento.
    O mesmo NOTEBOOKLM_HOME/PROFILE deve ser usado no login e processamento.
    """
    env = dict(os.environ)
    env["PREGACAO_PIPELINE_HOME"] = str(DATA_ROOT)
    return env


def extract_json(text: str) -> dict | list | None:
    """Extrai o primeiro objeto JSON embutido em uma saida de comando."""
    text = text.strip()
    for candidate in (text, text[text.find("{") :] if "{" in text else ""):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def find_id(obj, keys: tuple[str, ...]) -> str | None:
    """Procura recursivamente o primeiro valor de id em um JSON decodificado."""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v:
                return v
        for v in obj.values():
            found = find_id(v, keys)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_id(v, keys)
            if found:
                return found
    return None


def load_config() -> dict:
    """Defaults publicos; config local opcional, sem criar/copiar credenciais."""
    with open(CONFIG_TEMPLATE, encoding="utf-8") as fh:
        defaults = json.load(fh)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            configured = json.load(fh)
        if not isinstance(configured, dict):
            raise ValueError("A configuracao do pipeline deve ser um objeto JSON.")
        defaults.update(configured)
    return defaults


# ---------------------------------------------------------------------------
# Passos do pipeline
# ---------------------------------------------------------------------------


def step_download_from_drive(cfg: dict, name: str) -> Path:
    log(f"1. Baixando '{name}' do Google Drive")
    INBOX.mkdir(parents=True, exist_ok=True)
    dest = INBOX / Path(name).name
    run([RCLONE, "copyto", f"{cfg['drive_remote']}:{cfg['drive_folder']}/{name}", dest])
    return dest


def step_upload_to_drive(cfg: dict, audio: Path) -> None:
    log(f"2. Enviando '{audio.name}' para o Google Drive ({cfg['drive_remote']}:{cfg['drive_folder']})")
    run([RCLONE, "copyto", audio, f"{cfg['drive_remote']}:{cfg['drive_folder']}/{audio.name}"])


def step_notebooklm(cfg: dict, audio: Path, title: str) -> Path:
    log("3. Criando notebook no NotebookLM")
    proc = run([*NLM, "create", title, "--use", "--json"])
    notebook_id = find_id(extract_json(proc.stdout), ("notebook_id", "id", "notebook"))
    if notebook_id:
        print(f"   notebook: {notebook_id}")

    nb_args = ["-n", notebook_id] if notebook_id else []

    log(f"4. Adicionando o audio '{audio.name}' como fonte (transcricao pode levar minutos)")
    proc = run(
        [*NLM, "source", "add", audio, *nb_args, "--title", audio.stem, "--json"],
        timeout=300,
    )
    source_id = find_id(extract_json(proc.stdout), ("source_id", "id", "source"))
    if source_id:
        print(f"   fonte: {source_id}")
        run(
            [*NLM, "source", "wait", source_id, *nb_args, "--timeout", str(cfg["source_wait_timeout"])],
            timeout=cfg["source_wait_timeout"] + 60,
        )
    else:
        print("   (id da fonte nao recuperado; aguardando processamento por 60s)")
        import time

        time.sleep(60)

    log("5. Gerando o ESTUDO / DEVOCIONAL com o prompt definido")
    gen_cmd = [
        *NLM,
        "generate",
        "report",
        "--prompt-file",
        PROMPT_FILE,
        "--format",
        "custom",
        "--wait",
        "--timeout",
        str(cfg["report_timeout"]),
    ]
    if cfg.get("report_language"):
        gen_cmd += ["--language", cfg["report_language"]]
    gen_cmd += nb_args
    run(
        gen_cmd,
        timeout=cfg["report_timeout"] + 60,
    )

    log("6. Baixando o relatorio gerado")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT / f"estudo_{audio.stem}_{stamp}.md"
    run([*NLM, "download", "report", md_path, *nb_args, "--force"], timeout=300)
    if not md_path.exists() or md_path.stat().st_size == 0:
        raise SystemExit("ERRO: download do relatorio nao produziu arquivo.")
    return md_path


def step_md_to_pdf(md_path: Path) -> Path:
    log("7. Convertendo Markdown -> PDF")
    pdf_path = md_path.with_suffix(".pdf")
    code = r'''
import sys
from pathlib import Path
import markdown
from xhtml2pdf import pisa

md_path = Path(sys.argv[1])
pdf_path = Path(sys.argv[2])
body = markdown.markdown(
    md_path.read_text(encoding="utf-8"),
    extensions=["extra", "sane_lists"],
)
html = f"""<html><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 2cm; }}
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.45; color: #111; }}
  h1 {{ font-size: 18pt; text-align: center; margin-bottom: 4pt; }}
  h2 {{ font-size: 14pt; margin-top: 14pt; }}
  h3 {{ font-size: 12pt; margin-top: 10pt; }}
  li {{ margin-bottom: 4pt; }}
  strong {{ color: #000; }}
</style></head><body>{body}</body></html>"""
with open(pdf_path, "wb") as out:
    pisa.CreatePDF(html, dest=out, encoding="utf-8")
print(pdf_path)
'''
    run([PYTHON, "-c", code, md_path, pdf_path])
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise SystemExit("ERRO: conversao PDF falhou.")
    return pdf_path


def step_whatsapp(cfg: dict, pdf_path: Path, title: str, to: str | None, skip: bool) -> None:
    raw = (to or cfg.get("whatsapp_number") or "").strip()
    if skip:
        log("8. Envio por WhatsApp pulado (--skip-whatsapp)")
        return
    if not raw:
        log("8. Envio por WhatsApp pulado: defina 'whatsapp_number' em config.json ou use --to <numero>")
        return
    caption = f"Estudo/Devocional para Pequenos Grupos — {title}"
    recipients = []
    for part in re.split(r"[,;\s]+", raw):
        number = part.removeprefix("+")
        if not number.isdigit() or not 10 <= len(number) <= 15:
            raise SystemExit(f"ERRO: numero de WhatsApp invalido: {part}")
        if number not in recipients:
            recipients.append(number)
    if len(recipients) > 20:
        raise SystemExit("ERRO: limite de 20 numeros de destino")
    failures = []
    for recipient in recipients:
        log(f"8. Enviando PDF por WhatsApp para +{recipient}")
        result = run([NODE, WHATSAPP_SCRIPT, recipient, pdf_path, caption], check=False, timeout=180)
        output = (result.stdout or "") if result else ""
        match = re.search(r"^ACEITO:([^\r\n]+)", output, re.MULTILINE)
        if result and result.returncode == 0 and match:
            log(f"8. WhatsApp aceito pelo servidor para +{recipient} id={match.group(1).strip()}")
        else:
            log(f"8. WhatsApp falhou para +{recipient}")
            failures.append(recipient)
    if failures:
        raise SystemExit("ERRO: falha no WhatsApp para " + ", ".join("+" + n for n in failures))


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline: audio -> Drive -> NotebookLM -> PDF -> WhatsApp")
    parser.add_argument("audio", nargs="?", help="caminho do arquivo de audio local")
    parser.add_argument("--drive", metavar="NOME", help="baixar o audio do Drive antes de processar")
    parser.add_argument("--to", metavar="NUMERO", help="numero WhatsApp com DDI, ex.: 5511999999999")
    parser.add_argument("--title", metavar="TITULO", help="titulo do notebook/mensagem")
    parser.add_argument("--skip-drive", action="store_true", help="nao enviar o audio para o Drive")
    parser.add_argument("--skip-whatsapp", action="store_true", help="nao enviar o WhatsApp")
    args = parser.parse_args()

    cfg = load_config()

    if args.drive:
        audio = step_download_from_drive(cfg, args.drive)
    elif args.audio:
        audio = Path(args.audio).expanduser().resolve()
        if not audio.exists():
            raise SystemExit(f"ERRO: arquivo nao encontrado: {audio}")
    else:
        parser.error("informe o arquivo de audio ou use --drive <nome>")

    title = args.title or audio.stem.replace("_", " ")

    if not args.skip_drive and not args.drive:
        step_upload_to_drive(cfg, audio)

    md_path = step_notebooklm(cfg, audio, title)
    pdf_path = step_md_to_pdf(md_path)
    print(f"ARQUIVO_PDF:{pdf_path}", flush=True)

    step_whatsapp(cfg, pdf_path, title, args.to, args.skip_whatsapp)

    log("CONCLUIDO")
    print(f"  Markdown: {md_path}")
    print(f"  PDF:      {pdf_path}")


if __name__ == "__main__":
    main()
