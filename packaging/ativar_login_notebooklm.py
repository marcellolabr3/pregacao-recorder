"""Cria uma vez o token duravel do NotebookLM dentro deste projeto.

Uso: .venv\\Scripts\\python.exe -B packaging/ativar_login_notebooklm.py --account EMAIL
O navegador do Google abre uma vez; as renovacoes seguintes sao desassistidas.
O token fica em data/notebooklm/ e nunca deve ser enviado ao GitHub.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
HOME = ROOT / "data" / "notebooklm"
TOKEN = HOME / "profiles" / "default" / "master_token.json"
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _conta_existente() -> str:
    """Aproveita apenas o email da sessao antiga; cookies nao sao copiados."""
    storage = Path.home() / ".notebooklm/profiles/default/storage_state.json"
    try:
        value = json.loads(storage.read_text(encoding="utf-8"))
        return str(value["notebooklm"]["account"]["email"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def _validar_token(account: str) -> bool:
    if not TOKEN.exists():
        return False
    if TOKEN.is_symlink() or not TOKEN.is_file():
        raise ValueError("Arquivo do NotebookLM nao e um arquivo local normal")
    value = json.loads(TOKEN.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(
        isinstance(value.get(key), str) and value[key].strip()
        for key in ("email", "android_id", "master_token")
    ):
        raise ValueError("Token duravel do NotebookLM invalido")
    if value["email"].casefold() != account.casefold():
        raise ValueError("Ja existe um token para outra conta neste projeto")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", help="email da conta Google do NotebookLM")
    parser.add_argument("--browser", default="msedge" if os.name == "nt" else "chromium",
                        help="navegador para a autorizacao unica (padrao: msedge no Windows)")
    options = parser.parse_args(argv)
    account = (options.account or _conta_existente()
               or input("Email da conta Google do NotebookLM: ")).strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", account):
        parser.error("informe um email valido em --account")

    work = ROOT / ".w" / "login-notebooklm"
    work.mkdir(parents=True, exist_ok=True)
    HOME.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        NOTEBOOKLM_HOME=str(HOME),
        NOTEBOOKLM_PROFILE="default",
        PLAYWRIGHT_BROWSERS_PATH=str(ROOT / ".bundle-cache" / "browsers"),
        PIP_CACHE_DIR=str(ROOT / ".bundle-cache" / "pip"),
        TEMP=str(work), TMP=str(work), TMPDIR=str(work),
        PYTHONDONTWRITEBYTECODE="1",
    )
    env.pop("NOTEBOOKLM_AUTH_JSON", None)
    if not PYTHON.is_file():
        subprocess.run([sys.executable, "-B", "-m", "venv", str(PYTHON.parent.parent)],
                       cwd=ROOT, env=env, check=True)
    check = subprocess.run(
        [str(PYTHON), "-B", "-c",
         "import gpsoauth, notebooklm, playwright; "
         "import importlib.metadata as m; "
         "assert m.version('notebooklm-py') == '0.8.5'; "
         "assert m.version('playwright') == '1.64.0'"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if check.returncode:
        subprocess.run(
            [str(PYTHON), "-B", "-m", "pip", "install", "--disable-pip-version-check",
             "--no-cache-dir", "notebooklm-py[browser,headless]==0.8.5",
             "playwright==1.64.0"],
            cwd=ROOT, env=env, check=True,
        )

    if not _validar_token(account):
        if options.browser == "chromium":
            subprocess.run(
                [str(PYTHON), "-B", "-m", "playwright", "install", "chromium"],
                cwd=ROOT, env=env, check=True,
            )
        print("Abra a janela do Google e autorize esta conta uma vez.", flush=True)
        result = subprocess.run(
            [str(PYTHON), "-B", "-m", "notebooklm", "login", "--master-token",
             "--account", account, "--browser", options.browser],
            cwd=ROOT, env=env,
        )
        if result.returncode:
            raise RuntimeError("Login do NotebookLM nao concluido; confira a mensagem acima")
    if not _validar_token(account):
        raise RuntimeError("O login terminou sem criar o token duravel")
    subprocess.run(
        [str(PYTHON), "-B", "-m", "notebooklm", "auth", "refresh", "--verify"],
        cwd=ROOT, env=env, check=True,
    )
    print("NotebookLM configurado para renovacao automatica.")
    print("Token privado salvo em:", TOKEN)
    print("Agora gere novamente o instalador e o APK em dist-pacote-pessoal/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
