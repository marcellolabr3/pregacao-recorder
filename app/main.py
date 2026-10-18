"""Ponto de entrada do pregacao-recorder.

Sequencia de subida:

    boot -> systemd -> Recording Service -> Web API -> Interface web
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional, Tuple

from . import paths

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _bootstrap() -> None:
    paths.ensure_layout()
    from .config import load_env, config
    from .logging_setup import setup

    load_env()
    setup()
    config.reload()


def build() -> Tuple[Any, Any, Any]:
    """Cria Flask app, manager e uploader."""
    from flask import Flask, render_template

    from .api.routes import register_routes
    from .db import db
    from .logging_setup import get
    from .recording import recovery
    from .recording.manager import RecordingManager
    from .states import State, state_machine
    from .upload.queue import UploadWorker
    from .config import config

    log = get("main")

    # 1. recupera gravacoes interrompidas ANTES de aceitar novas
    interrupted = recovery.scan(db, config.recordings_root)
    if interrupted:
        state_machine.set(
            State.RECOVERY_REQUIRED,
            detail=f"{len(interrupted)} gravacao(oes) interrompida(s)",
            force=True,
        )
        log.warning("detectadas %d gravacoes interrompidas", len(interrupted))

    # 2. worker de upload persistente
    uploader = UploadWorker(config, db)
    uploader.start()

    # 3. gerenciador de gravacao
    manager = RecordingManager(config, db, uploader)

    # 4. app web
    app = Flask(
        "pregacao-recorder",
        template_folder=str(WEB_DIR / "templates"),
        static_folder=str(WEB_DIR / "static"),
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = config.secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 12
    app.config["JSON_SORT_KEYS"] = False
    # garante que alteracoes no HTML aparecam sem reiniciar o servico
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    @app.route("/")
    @app.route("/config")
    @app.route("/historico")
    def index():  # type: ignore[no-untyped-def]
        return render_template("index.html", device_name=config.get("device_name", "Pulpito"))

    register_routes(app, manager, uploader)
    log.info("aplicacao pronta; interface em http://<ip-do-pi>:%d", config.port)
    return app, manager, uploader


def _install_signal_handlers(manager, uploader) -> None:  # pragma: no cover
    def handler(signum, _frame):  # type: ignore[no-untyped-def]
        from .logging_setup import get
        from .notify import notify
        from .states import State, state_machine

        log = get("main")
        log.info("sinal %s recebido; encerrando graciosamente", signum)
        try:
            if state_machine.state == State.RECORDING and manager.recorder:
                # Para a captura mantendo os segmentos: a proxima subida oferece
                # recuperacao pela interface. Nenhum audio e perdido.
                manager.recorder.stop()
                progress = manager.recorder.progress()
                if manager.session_id:
                    manager.db.update_session(
                        manager.session_id,
                        segments=progress["segments"],
                        bytes=progress["bytes"],
                        duration_secs=progress["duration"],
                    )
                notify(
                    "servico_parado",
                    "Servico encerrado durante a gravacao; segmentos preservados",
                    level="warning",
                )
            uploader.stop()
        finally:
            log.info("encerramento concluido")
            os._exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def _so_uma_instancia(log) -> bool:
    """Impede duas instancias do servidor no mesmo equipamento.

    A segunda brigaria pela porta e, antes de perder, ja teria subido
    recuperacao de gravacoes, uploader e fila de estudos - trabalho
    duplicado (nenhuma etapa pode rodar duas vezes).
    """
    from .remote.agent import TravaInstancia

    caminho = paths.home() / "logs" / "servidor.pid"
    if not TravaInstancia(caminho).adquirir():
        log.error(
            "outra instancia do pregacao-recorder ja esta rodando "
            "(pid em %s); encerre a outra antes de iniciar esta",
            caminho,
        )
        return False
    return True


def run(host: Optional[str] = None, port: Optional[int] = None) -> Optional[bool]:
    _bootstrap()
    from .config import config
    from .logging_setup import get

    log = get("main")
    if not _so_uma_instancia(log):
        return False
    app, manager, uploader = build()
    _install_signal_handlers(manager, uploader)

    host = host or config.host
    port = port or config.port

    try:
        from waitress import serve
    except ImportError:  # pragma: no cover - fallback de desenvolvimento
        log.warning("waitress nao instalado; usando servidor de desenvolvimento")
        app.run(host=host, port=port, threaded=True, use_reloader=False)
        return

    log.info("servidor iniciado em %s:%s", host, port)
    serve(app, host=host, port=port, threads=6, ident="pregacao-recorder")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="pregacao-recorder")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--recovery-scan", action="store_true",
                        help="apenas verifica gravacoes interrompidas e sai")
    args = parser.parse_args(argv)

    _bootstrap()
    if args.recovery_scan:
        from .config import config
        from .db import db
        from .recording import recovery

        items = recovery.scan(db, config.recordings_root)
        for item in items:
            print(f"INTROMPIDA {item['id']} duration={item['duration']:.0f}s "
                  f"segments={item['segments']} bytes={item['bytes']}")
        print(f"{len(items)} gravacao(oes) interrompida(s)")
        return 0

    iniciou = run(args.host, args.port)
    return 1 if iniciou is False else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
