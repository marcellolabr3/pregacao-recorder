"""Comando de linha ``pregacao`` - diagnostico do equipamento sem monitor."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Dict, Optional

from . import paths
from .config import config, load_env
from .logging_setup import setup as setup_logging

SERVICE = "pregacao-recorder.service"


def _base_url() -> str:
    return f"http://127.0.0.1:{config.port}"


def _client(pin: Optional[str] = None):
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return opener


def _request(opener, method: str, path: str, payload: Optional[Dict] = None):
    url = _base_url() + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read().decode() or "{}")


def _service_action(action: str) -> str:
    import subprocess

    try:
        proc = subprocess.run(
            ["systemctl", action, SERVICE], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"erro: {exc}"
    return (proc.stdout or proc.stderr or "").strip()


def _human_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _human_duration(seconds: float) -> str:
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
def cmd_status(_args) -> int:
    opener = _client()
    try:
        status = _request(opener, "GET", "/api/status")
    except (urllib.error.URLError, OSError) as exc:
        print("SERVICO FORA DO AR")
        print(f"  erro: {exc}")
        print("  tente: sudo systemctl status pregacao-recorder")
        return 2

    banner = {
        "PRONTO": "PRONTO",
        "GRAVANDO": "GRAVANDO",
        "ENVIANDO": "ENVIANDO",
        "ATENCAO": "ATENCAO",
    }.get(status.get("banner", ""), status.get("banner", "?"))

    print("=" * 58)
    print(f"  {status.get('device_name', 'pregacao-recorder')}  -  {banner}")
    print("=" * 58)
    print(f"  Estado            : {status.get('state')}")
    print(f"  Detalhe           : {status.get('detail') or '-'}")

    rec = status.get("recording") or {}
    if status.get("state") == "RECORDING":
        print(f"  Duracao           : {_human_duration(rec.get('duration', 0))}")
        print(f"  Segmentos         : {rec.get('segments', 0)}")
        print(f"  Bytes capturados  : {_human_bytes(rec.get('bytes', 0))}")

    device = status.get("device") or {}
    print(f"  Audio             : {device.get('hw', 'auto')} ({device.get('name', '?')})")

    disk = status.get("storage") or {}
    if disk.get("ok"):
        print(f"  Armazenamento     : {disk.get('free_mb')} MB livres "
              f"({disk.get('used_percent')}% usado) em {disk.get('path')}")

    net = status.get("network") or {}
    print(f"  Internet          : {'OK' if net.get('online') else 'SEM CONEXAO'}")

    drive_info = status.get("drive") or {}
    conectado = "conectado" if drive_info.get("connected") else "DESCONECTADO"
    print(f"  Google Drive      : {conectado}")

    uploads = status.get("uploads") or {}
    print(f"  Uploads pendentes : {uploads.get('pending', 0)}"
          f"   concluidos: {uploads.get('done', 0)}")

    recovery_items = status.get("recovery") or []
    if recovery_items:
        print("-" * 58)
        print(f"  ! {len(recovery_items)} gravacao(oes) interrompida(s):")
        for item in recovery_items:
            print(f"      {item.get('id')}  "
                  f"duracao={_human_duration(item.get('duration', 0))}  "
                  f"segmentos={item.get('segments')}  "
                  f"tamanho={_human_bytes(item.get('bytes', 0))}")
        print("      recupere pela interface web: http://<ip-do-pi>/")

    last = status.get("last_recording")
    if last:
        print("-" * 58)
        print(f"  Ultima gravacao   : {os.path.basename(last.get('final_path') or '-')}")
        print(f"                      {_human_bytes(last.get('final_bytes') or 0)}"
              f"  estado={last.get('state')}")

    print("=" * 58)
    return 0 if status.get("state") != "ERROR" else 1


def cmd_check(_args) -> int:
    """Prova que o Raspberry esta realmente capturando audio."""
    from .audio import device as audio_device

    setup_logging()
    detected = audio_device.detect(str(config.get("audio.device", "auto")))
    print(f"Dispositivo selecionado: {detected.get('hw')} - {detected.get('name')}")
    devices = audio_device.list_devices()
    if not devices:
        print("NENHUMA interface de audio encontrada pelo ALSA.")
        print("Veja docs/AUDIO.md para configurar a interface USB.")
        return 1
    print("Interfaces disponiveis:")
    for dev in devices:
        mark = "<- selecionado" if dev["hw"] == detected.get("hw") else ""
        print(f"  {dev['hw']:12} {dev['name']} {mark}")

    print("\nCapturando 2 segundos de audio...")
    level = audio_device.capture_level(2.0, detected.get("hw"))
    if not level.get("ok"):
        print(f"FALHA: {level.get('error')}")
        return 1
    print(f"  amostras : {level.get('samples')}")
    print(f"  pico     : {level.get('peak')} ({level.get('peak_db')} dBFS)")
    print(f"  rms      : {level.get('rms')}")
    if level.get("silent"):
        print("\n[SILENCIO] O Raspberry captura, mas nao ha sinal.")
        print("  -> Suba o fader do canal na mesa Soundcraft.")
        print("  -> Verifique o cabecalho USB e o canal selecionado (MAIN/L-R).")
        return 1
    print("\nOK: ha sinal de audio chegando ao Raspberry.")
    return 0


def cmd_start(_args) -> int:
    return _simple_action("POST", "/api/start")


def cmd_stop(_args) -> int:
    return _simple_action("POST", "/api/stop")


def _simple_action(method: str, path: str) -> int:
    opener = _client()
    try:
        _request(opener, "POST", "/api/login", {"pin": config.pin})
    except (urllib.error.URLError, OSError) as exc:
        print(f"servico indisponivel: {exc}")
        return 2
    try:
        result = _request(opener, method, path)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"falha ({exc.code}): {body}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_logs(args) -> int:
    import subprocess

    cmd = ["journalctl", "-u", SERVICE, "-n", str(args.lines), "--no-pager"]
    if args.follow:
        cmd += ["-f"]
    try:
        return subprocess.call(cmd)
    except OSError:
        log_file = paths.logs_dir() / "pregacao.log"
        if not log_file.exists():
            print("nenhum log encontrado")
            return 1
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-args.lines:]:
            print(line)
        return 0


def cmd_doctor(_args) -> int:
    """Checagem completa de saude do equipamento."""
    setup_logging()
    ok = True

    def check(label: str, condition: bool, hint: str = "") -> None:
        nonlocal ok
        print(f"  [{'OK' if condition else 'XX'}] {label}")
        if not condition:
            ok = False
            if hint:
                print(f"        -> {hint}")

    print("Diagnostico pregacao-recorder")
    for name, directory in [
        ("diretorio base", paths.home()),
        ("config", paths.config_dir()),
        ("gravacoes", config.recordings_root),
        ("logs", paths.logs_dir()),
        ("banco", paths.data_dir()),
    ]:
        check(f"{name}: {directory}", directory.exists() and os.access(directory, os.W_OK),
              "verifique permissoes: sudo chown -R pi:pi " + str(directory))

    import shutil as _shutil

    check("arecord (alsa-utils)", bool(_shutil.which("arecord")),
          "sudo apt install alsa-utils")
    check("ffmpeg (conversao mp3)", bool(_shutil.which("ffmpeg")),
          "sudo apt install ffmpeg  (sem ele, o sistema grava WAV)")

    from .audio import device as audio_device

    devices = audio_device.list_devices()
    check("interface de audio", bool(devices),
          "conecte a interface USB e rode: arecord -l")

    check("google drive configurado", config.google_credentials_file.exists(),
          "veja docs/GOOGLE_DRIVE.md")

    # Sem PREGACAO_PIN o proprio codigo abre o painel sem autenticacao
    # (auth.is_authenticated() devolve True) - e' uma decisao de instalacao,
    # nao uma falha de saude. Por isso imprime o estado em vez de marcar XX.
    from .api import auth as _auth

    print(f"  [{'OK' if _auth.pin_configured() else '--'}] painel web: "
          + ("pede PIN ao abrir" if _auth.pin_configured()
             else "SEM PIN - abre direto para quem estiver na rede"))
    if not _auth.pin_configured():
        print("        -> para voltar a exigir: defina PREGACAO_PIN "
              "no arquivo /opt/pregacao-recorder/.env")
    print(f"  [{'OK' if _auth.admin_configured() else '--'}] "
          "CONFIGURACOES AVANCADAS: "
          + ("pede PIN de administrador" if _auth.admin_configured()
             else "SEM PIN - abertas para quem estiver na rede"))

    try:
        opener = _client()
        status = _request(opener, "GET", "/api/status")
        check("servico web respondendo", True)
        print(f"        estado atual: {status.get('state')}")
    except Exception as exc:  # noqa: BLE001
        check("servico web respondendo", False, str(exc))

    print("RESULTADO:", "TUDO OK" if ok else "PROBLEMAS ENCONTRADOS")
    return 0 if ok else 1


def cmd_recovery_list(_args) -> int:
    from .config import config as cfg
    from .db import db
    from .recording import recovery

    items = recovery.scan(db, cfg.recordings_root)
    if not items:
        print("Nenhuma gravacao interrompida.")
        return 0
    for item in items:
        print(f"{item['id']}")
        print(f"  inicio   : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['started_at']))}")
        print(f"  duracao  : {_human_duration(item['duration'])}")
        print(f"  segmentos: {item['segments']}")
        print(f"  tamanho  : {_human_bytes(item['bytes'])}")
        print(f"  motivo   : {item['reason']}")
        print(f"  dir      : {item['dir']}")
    return 1


def cmd_service(args) -> int:
    print(_service_action(args.action))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pregacao",
        description="Ferramenta de diagnostico do pregacao-recorder",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="estado atual do sistema").set_defaults(func=cmd_status)
    sub.add_parser("check", help="verifica se ha sinal de audio").set_defaults(func=cmd_check)
    sub.add_parser("start", help="inicia uma gravacao").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="finaliza a gravacao em andamento").set_defaults(func=cmd_stop)
    sub.add_parser("doctor", help="checagem completa de saude").set_defaults(func=cmd_doctor)
    sub.add_parser("recovery", help="lista gravacoes interrompidas").set_defaults(
        func=cmd_recovery_list
    )

    logs = sub.add_parser("logs", help="mostra os logs do servico")
    logs.add_argument("-n", "--lines", type=int, default=80)
    logs.add_argument("-f", "--follow", action="store_true")
    logs.set_defaults(func=cmd_logs)

    service = sub.add_parser("service", help="controla o servico systemd")
    service.add_argument(
        "action", choices=["start", "stop", "restart", "status", "enable", "disable"]
    )
    service.set_defaults(func=cmd_service)

    return parser


def main(argv: Optional[list] = None) -> int:
    load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
