"""Acesso remoto via Tailscale (VPN privada, sem port forwarding).

Decisoes de seguranca:

* o painel NUNCA expoe o Raspberry direto a Internet; o caminho remoto e
  sempre_TUNNEL Tailscale (rede 100.x);
* o servico web roda como ``aska`` e o binario do tailscale exige root, entao
  a execucao passa por ``sudo -n`` com uma lista fechada de comandos gravada
  em ``/etc/sudoers.d/pregacao-network`` (instalada pelo install.sh);
* nada de senha/chave e devolvido pela API: apenas o link de autenticacao
  gerado pelo proprio Tailscale (login.tailscale.com).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
from typing import Any, Dict, Optional

from ..logging_setup import get

log = get("tailscale")

# comandos aceitos pelo sudoers (devem bater exatamente)
CMD_STATUS_JSON = ["status", "--json"]
CMD_UP = ["up"]
CMD_VERSION = ["version"]

_pending: Optional[threading.Thread] = None
_pending_lock = threading.Lock()


def installed() -> bool:
    return shutil.which("tailscale") is not None


def _sudo(args, timeout: int = 30):
    """Roda ``tailscale <args>`` como root via sudo sem senha. (rc, out, err)"""
    cmd = ["sudo", "-n", "/usr/bin/tailscale", *[str(a) for a in args]]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout)
    except FileNotFoundError:
        return 127, "", "sudo nao encontrado"
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def status() -> Dict[str, Any]:
    """Status do Tailscale para o painel. Nunca lanca excecao."""
    base: Dict[str, Any] = {
        "installed": False,
        "running": False,
        "connected": False,
        "login_required": False,
        "backend_state": "",
        "hostname": "",
        "dns_name": "",
        "ip": "",
        "auth_url": "",
        "version": "",
        "message": "Tailscale nao instalado",
        "logging_in": False,
    }
    if not installed():
        return base

    base["installed"] = True
    base["message"] = ""
    code, out, err = _sudo(CMD_STATUS_JSON, timeout=20)
    if code != 0:
        base["message"] = _friendly(err or out)
        base["login_required"] = base["message"].lower().find("login") >= 0
        base["logging_in"] = _login_running()
        return base

    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        base["message"] = "saida invalida do tailscale"
        return base

    state = str(data.get("BackendState", ""))
    base["backend_state"] = state
    base["auth_url"] = str(data.get("AuthURL") or "")
    base["running"] = state == "Running"
    base["login_required"] = state in ("NoState", "NeedsLogin", "NeedsMachineAuth")
    base["logging_in"] = _login_running() or bool(base["auth_url"])

    itself = data.get("Self") or {}
    ips = itself.get("TailscaleIPs") or []
    base["hostname"] = str(itself.get("HostName") or "")
    base["dns_name"] = str(itself.get("DNSName") or "").rstrip(".")
    base["ip"] = next((str(i) for i in ips if str(i).startswith("100.")), "") \
        or (str(ips[0]) if ips else "")
    base["connected"] = bool(state == "Running" and itself.get("Online")
                             and base["ip"])

    if state == "Running" and not base["connected"]:
        base["message"] = "conectado ao Tailscale mas sem IP valido"
    elif state == "Stopped":
        base["message"] = "Tailscale desativado"
    elif base["login_required"]:
        base["message"] = "autenticacao pendente"
    return base


def _friendly(raw: str) -> str:
    text = " ".join((raw or "").split())
    lowered = text.lower()
    if "failed to connect" in lowered or "no such file" in lowered:
        return "servico tailscaled parado"
    if "permission denied" in lowered or "password is required" in lowered:
        return "sem permissao (sudoers ausente)"
    if "needs login" in lowered or "logged out" in lowered:
        return "autenticacao pendente"
    return text[:200] or "sem status"


def _login_running() -> bool:
    thread = _pending
    return bool(thread and thread.is_alive())


def start_login(wait: int = 8) -> Dict[str, Any]:
    """Dispara ``tailscale up`` em segundo plano e devolve o link de login.

    O ``tailscale up`` bloqueia ate o usuario autenticar; por isso ele roda
    em uma thread com limite de tempo e a interface fica consultando
    ``status()`` (campo ``auth_url``) ate aparecer o link.
    """
    info = status()
    if not info["installed"]:
        return {"started": False, "message": info["message"]}
    if info["connected"]:
        return {"started": False, "auth_url": "", "message": "ja conectado"}
    if info["auth_url"]:
        return {"started": True, "auth_url": info["auth_url"], "message": ""}

    with _pending_lock:
        if _login_running():
            return {"started": True, "auth_url": info["auth_url"],
                    "message": "autenticacao em andamento"}
        thread = threading.Thread(target=_login_worker, daemon=True,
                                  name="tailscale-login")
        _set_pending(thread)
        thread.start()

    # espera curta para tentar devolver o link ja na primeira resposta
    import time
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(1)
        info = status()
        if info["auth_url"]:
            return {"started": True, "auth_url": info["auth_url"], "message": ""}
        if info["connected"]:
            return {"started": True, "auth_url": "", "message": "conectado"}
    return {"started": True, "auth_url": info["auth_url"],
            "message": "aguardando link de autenticacao"}


def _set_pending(thread: threading.Thread) -> None:
    global _pending
    _pending = thread


def _login_worker() -> None:
    log.info("[TAILSCALE] iniciando autenticacao (tailscale up)")
    code, out, err = _sudo(CMD_UP, timeout=600)
    if code == 0:
        log.info("[TAILSCALE] autenticacao concluida")
    else:
        log.warning("[TAILSCALE] autenticacao nao concluida: %s",
                    _friendly(err or out))


def version() -> str:
    if not installed():
        return ""
    code, out, _ = _sudo(CMD_VERSION, timeout=15)
    if code != 0:
        return ""
    return out.strip().splitlines()[0] if out.strip() else ""
