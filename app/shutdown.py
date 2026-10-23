"""Encerra apenas os processos desta instalacao antes de atualizar/desinstalar."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from . import bundled_runtime, launcher
from .config import Config, load_env
from .remote.agent import LocalApi


def pending_work(db_file: Path) -> bool:
    if not db_file.is_file():
        return False
    with sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True, timeout=5) as conn:
        checks = (
            ("uploads", "status = 'RUNNING'"),
            ("jobs", "estado = 'EXECUTANDO'"),
            ("whatsapp_sends", "status = 'PENDENTE'"),
        )
        return any(conn.execute(f"SELECT 1 FROM {table} WHERE {condition} LIMIT 1").fetchone()
                   for table, condition in checks)


def stop() -> int:
    root = Path(__file__).resolve().parent.parent
    bundled_runtime.prepare_environment(create_config=False, recorder_root=root)
    home = Path(os.environ.get("PREGACAO_HOME") or root)
    load_env(home / ".env")
    cfg = Config(home)
    pids = {}
    for component, name in launcher.PID_FILES.items():
        pids[component] = launcher.running_pid(home / "logs" / name, component, root, home)
    if pending_work(home / "data" / "pregacao.db"):
        print("Ha upload, estudo ou envio em andamento; conclua antes de continuar.")
        return 2
    if pids["gravador"]:
        host = str(getattr(cfg, "host", "0.0.0.0") or "0.0.0.0")
        host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
        url = f"http://{'[' + host + ']' if ':' in host else host}:{cfg.port}"
        code, status = LocalApi(url, cfg.pin, timeout=5).status()
        if code != 200 or not isinstance(status, dict) or status.get("device_id") != cfg.device_id:
            print("Nao foi possivel confirmar o estado do gravador; nenhum processo foi encerrado.")
            return 4
        uploads = status.get("uploads") or {}
        if ((status.get("recording") or {}).get("active")
                or status.get("state") in ("RECORDING", "FINALIZING")
                or int(uploads.get("running") or 0)):
            print("Ha gravacao, upload, estudo ou envio pendente; conclua antes de continuar.")
            return 2
    for component in ("agente", "gravador"):
        pid = pids[component]
        if pid:
            result = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                    capture_output=True, creationflags=launcher._creationflags())
            if result.returncode and launcher.running_pid(home / "logs" / launcher.PID_FILES[component],
                                                           component, root, home):
                print("Nao foi possivel encerrar o servico " + component)
                return 3
    tray = root.parent / "Bandeja.ps1"
    if tray.is_file():
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                                 "Bypass", "-File", str(tray), "-Stop"],
                                capture_output=True, creationflags=launcher._creationflags(), timeout=20)
        if result.returncode:
            print("A bandeja nao respondeu ao encerramento; tente novamente.")
            return 3
    return 0


def main() -> int:
    try:
        return stop()
    except (OSError, ValueError, sqlite3.Error, launcher.LaunchError) as exc:
        print("Nao foi possivel confirmar uma parada segura: " + str(exc))
        return 4


if __name__ == "__main__":
    sys.exit(main())
