"""Inicializacao Windows, sem alterar o funcionamento dos dois servicos."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser


MODULES = {"gravador": "app.main", "agente": "app.remote.agent"}
PID_FILES = {"gravador": "servidor.pid", "agente": "agente.pid"}
LOG_FILES = {"gravador": "pregacao.log", "agente": "pregacao-agente.log"}


class LaunchError(RuntimeError):
    """Falha de inicializacao que pode ser apresentada ao operador."""


def _creationflags() -> int:
    return subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def dependency_check(component: str) -> list[str]:
    names = {
        "gravador": ("flask", "werkzeug", "waitress"),
        "agente": ("paho.mqtt.client",),
        "drive": ("googleapiclient.discovery", "google_auth_oauthlib", "google_auth_httplib2"),
    }[component]
    missing = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception:
            missing.append(name)
    return missing


def process_command(pid: int) -> list[str] | None:
    """Consulta identidade, sem enviar sinais nem confiar em PID reutilizado."""
    if pid <= 0:
        return None
    if os.name != "nt":
        try:
            return Path(f"/proc/{pid}/cmdline").read_bytes().decode().strip("\0").split("\0")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise LaunchError("Nao foi possivel conferir os processos existentes.") from exc
    # O PID e um inteiro; nao ha interpolacao de caminhos ou valores do .env.
    command = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}'; "
        "if ($p) { $p.CommandLine | ConvertTo-Json -Compress }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, encoding="utf-8-sig", timeout=10,
            creationflags=_creationflags(), check=True,
        )
        if not result.stdout.strip():
            return None
        raw = json.loads(result.stdout)
        if not isinstance(raw, str) or not raw:
            raise ValueError("identidade indisponivel")
        import ctypes
        from ctypes import wintypes

        shell = ctypes.WinDLL("shell32", use_last_error=True)
        shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel.LocalFree.restype = wintypes.HLOCAL
        count = ctypes.c_int()
        args = shell.CommandLineToArgvW(raw, ctypes.byref(count))
        if not args:
            raise ValueError("linha de comando indisponivel")
        try:
            return [args[i] for i in range(count.value)]
        finally:
            kernel.LocalFree(args)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise LaunchError("Nao foi possivel identificar um PID existente; nenhum processo foi reiniciado.") from exc


def running_pid(pid_file: Path, component: str) -> int | None:
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None
    except OSError as exc:
        raise LaunchError(f"Nao foi possivel ler {pid_file.name}.") from exc
    args = process_command(pid)
    if args is None:
        return None
    # Conferir tambem o interpretador: outro projeto nao e esta instalacao.
    python = Path(args[0]).resolve() if args else None
    allowed = {Path(sys.executable).resolve()}
    base_python = getattr(sys, "_base_executable", None)
    if base_python:
        allowed.add(Path(base_python).resolve())
    module_args = args[args.index("-m") + 1:] if "-m" in args else []
    matches = module_args == [MODULES[component]] or module_args == ["app.launcher", "--service", component]
    if python not in allowed or not matches:
        raise LaunchError(f"{pid_file.name} aponta para outro processo; nenhum processo foi alterado.")
    return pid


@contextmanager
def _launch_lock(home: Path):
    """Serializa cliques simultaneos, inclusive durante a espera da API."""
    folder = home / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "inicializacao.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + 45
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LaunchError("Outra inicializacao esta em andamento. Aguarde e tente novamente.") from exc
                time.sleep(0.2)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)


def _api_ready(url: str) -> bool:
    try:
        # Ignorar proxies do ambiente somente para esta consulta local.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url + "/api/me", timeout=1) as response:
            data = json.loads(response.read(65536))
            return response.status == 200 and isinstance(data, dict) and all(
                key in data for key in ("device_name", "state", "setup_needed")
            )
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _port_available(url: str) -> bool:
    address = urllib.parse.urlsplit(url)
    try:
        ipv6 = ":" in (address.hostname or "")
        family = socket.AF_INET6 if ipv6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("::" if ipv6 else "0.0.0.0", address.port or 8080))
        return True
    except OSError:
        return False


def wait_ready(url: str, child=None, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child is not None and child.poll() is not None:
            raise LaunchError("O gravador encerrou ao iniciar. Consulte logs/pregacao.log e logs/inicio-gravador.log.")
        if _api_ready(url):
            return
        time.sleep(0.2)
    raise LaunchError("O painel ainda nao respondeu. Consulte os logs; nenhum processo foi encerrado. Tente abrir novamente.")


def _wait_agent(child, pid_file: Path, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise LaunchError("O agente encerrou ao iniciar. Consulte logs/pregacao-agente.log e logs/inicio-agente.log.")
        if running_pid(pid_file, "agente"):
            return
        time.sleep(0.2)
    raise LaunchError("O agente ainda nao confirmou a inicializacao. Consulte logs/pregacao-agente.log.")


def launch(component: str, root: Path, home: Path, env: dict, url: str, timeout: float = 30.0) -> bool:
    pid_file = home / "logs" / PID_FILES[component]
    if running_pid(pid_file, component):
        if component == "gravador":
            wait_ready(url, timeout=timeout)
        return False
    if component == "gravador" and not _port_available(url):
        raise LaunchError("A porta do painel esta ocupada por outro processo. Nenhum servico foi iniciado ou reiniciado.")
    missing = dependency_check(component)
    if missing:
        raise LaunchError("Dependencias ausentes: " + ", ".join(missing) + ". Consulte docs/WINDOWS.md.")
    if component == "gravador" and not shutil.which("ffmpeg", path=env.get("PATH")):
        raise LaunchError("FFmpeg ausente no PATH. Consulte docs/WINDOWS.md.")
    child_env = dict(env, PREGACAO_HOME=str(home), PREGACAO_LOG_FILE=LOG_FILES[component])
    child = subprocess.Popen(
        [sys.executable, "-B", "-m", "app.launcher", "--service", component],
        cwd=str(root), env=child_env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True, creationflags=_creationflags(),
    )
    if component == "gravador":
        wait_ready(url, child=child, timeout=timeout)
    else:
        _wait_agent(child, pid_file, timeout)
    return True


def _run_service(component: str, home: Path) -> int:
    """Preserva as entradas atuais; registra inclusive erros antes do bootstrap."""
    log = _file_logger(home, "inicio-" + component)
    try:
        runpy.run_module(MODULES[component], run_name="__main__", alter_sys=True)
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
        if code:
            log.error("Servico encerrou na inicializacao (codigo %s). Consulte %s.", code, LOG_FILES[component])
        return code
    except Exception:
        log.exception("Falha ao executar o servico %s", component)
        return 1


def _file_logger(home: Path, name: str) -> logging.Logger:
    (home / "logs").mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("pregacao-launcher." + name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(home / "logs" / (name + ".log"), maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def diagnostic(cfg, env: dict) -> int:
    """Somente leitura: nao importa o backend nem inicia filas, logins ou MQTT."""
    ok = True

    def check(label: str, condition: bool, required: bool = False):
        nonlocal ok
        print(f"[{'OK' if condition else 'FALTA' if required else 'AVISO'}] {label}")
        if required and not condition:
            ok = False

    check("Python 3.11 ou superior", sys.version_info >= (3, 11), True)
    check("dependencias do gravador", not dependency_check("gravador"), True)
    check("bibliotecas do Google Drive", not dependency_check("drive"))
    for tool in ("ffmpeg", "ffprobe", "node", "rclone"):
        check(tool + " no PATH", bool(shutil.which(tool, path=env.get("PATH"))), tool == "ffmpeg")
    remote = bool(env.get("PREGACAO_REMOTE_HOST", "").strip()) and env.get("PREGACAO_REMOTE_ENABLED", "auto").lower().strip() not in {"0", "false", "no", "off", "desligado"}
    if remote:
        check("dependencias do controle remoto", not dependency_check("agente"))
        print("[INFO] Controle remoto configurado; conexao sera confirmada no painel.")
    else:
        print("[INFO] Controle remoto desativado ou ainda nao configurado.")
    check("destino de gravacoes disponivel", cfg.recordings_root.is_dir())
    drive_credentials = cfg.google_credentials_file.is_file() or bool(
        cfg.get("drive.client_id", "") and cfg.get("drive.client_secret", "")
    ) or bool(env.get("GOOGLE_CLIENT_ID", "").strip() and env.get("GOOGLE_CLIENT_SECRET", "").strip())
    check("credenciais do Drive configuradas", drive_credentials)
    check("token local do Drive presente", cfg.google_token_file.is_file())
    folder = str(cfg.get("estudos.pasta", "") or "").strip()
    python = str(cfg.get("estudos.python", "") or "").strip()
    if folder or python:
        check("pasta e pipeline de estudos presentes", bool(folder) and (Path(folder) / "pipeline.py").is_file())
        check("Python do pipeline presente", bool(python) and Path(python).is_file())
        print("[INFO] Login NotebookLM e sessao WhatsApp: conferir no painel quando necessario.")
    else:
        print("[INFO] Pipeline de estudos ainda nao configurado.")
    print("Verificacao concluida. Nenhum servico, captura ou envio foi iniciado.")
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inicia o Pregacao Recorder e seu controle remoto.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--verificar", action="store_true", help="confere requisitos sem iniciar servicos")
    modes.add_argument("--somente-gravador", action="store_true", help="inicia somente o servidor")
    modes.add_argument("--somente-agente", action="store_true", help="inicia somente o controle remoto")
    parser.add_argument("--sem-navegador", action="store_true", help="inicia sem abrir o painel")
    parser.add_argument("--service", choices=MODULES, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent.parent
    home = Path(os.environ.get("PREGACAO_HOME") or root).resolve()
    os.environ["PREGACAO_HOME"] = str(home)
    if args.service:
        # Nao entregar os argumentos privados ao argparse do servico original.
        sys.argv = [MODULES[args.service]]
        return _run_service(args.service, home)
    try:
        from .config import Config, load_env

        load_env(home / ".env")
        cfg = Config(home)
    except (OSError, ValueError):
        print("[ERRO] Nao foi possivel ler a configuracao local. Confira permissoes e formato JSON.")
        return 1
    env = dict(os.environ)
    # Equivale ao PATH/ambiente do activate.bat, usando o Python explicito.
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["VIRTUAL_ENV"] = sys.prefix
    if args.verificar:
        return diagnostic(cfg, env)
    log = None
    try:
        if sys.version_info < (3, 11):
            raise LaunchError("Python 3.11 ou superior e necessario.")
        if not 1 <= cfg.port <= 65535:
            raise LaunchError("Porta do painel invalida. Confira a configuracao existente.")
        host = str(getattr(cfg, "host", "0.0.0.0") or "0.0.0.0")
        host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
        url = f"http://{'[' + host + ']' if ':' in host else host}:{cfg.port}"
        if not env.get("PREGACAO_API_BASE", "").strip():
            env["PREGACAO_API_BASE"] = url
        with _launch_lock(home):
            log = _file_logger(home, "inicializacao")
            if not args.somente_agente:
                created = launch("gravador", root, home, env, url)
                print("[OK] Gravador " + ("iniciado." if created else "ja estava em execucao."))
                log.info("Gravador pronto em %s", url)
            remote = bool(env.get("PREGACAO_REMOTE_HOST", "").strip()) and env.get("PREGACAO_REMOTE_ENABLED", "auto").lower().strip() not in {"0", "false", "no", "off", "desligado"}
            result = 0
            if not args.somente_gravador and remote:
                try:
                    created = launch("agente", root, home, env, url)
                    print("[OK] Agente " + ("iniciado; confirme a conexao no painel." if created else "ja estava em execucao."))
                    log.info("Agente em execucao")
                except (LaunchError, OSError) as exc:
                    print(f"[AVISO] Controle remoto: {exc}")
                    print("O gravador continua funcionando de forma independente.")
                    log.warning("Falha ao iniciar agente: %s", exc)
                    result = 1
            elif not args.somente_gravador:
                print("[INFO] Controle remoto desativado ou ainda nao configurado.")
            if not args.somente_agente:
                print("Painel: " + url)
                if not args.sem_navegador:
                    try:
                        webbrowser.open(url)
                    except OSError:
                        print("Abra o endereco acima no navegador.")
            return result
    except (LaunchError, OSError) as exc:
        print(f"[ERRO] {exc}")
        if log:
            log.error("Inicializacao incompleta: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
