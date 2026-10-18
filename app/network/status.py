"""Status de rede estruturado para a interface (GET /api/network/status).

Nunca devolve senha, chave ou credencial -- apenas endereco, estado e nome de
rede. O JSON segue o formato combinado na arquitetura do projeto:

    {
      "ethernet":  {connected, ip, gateway, ...},
      "wifi":      {connected, ssid, ip, signal, ...},
      "internet":  {connected, ...},
      "accessPoint": {active, ssid, ip, ...},
      "tailscale": {connected, ip, ...},
      "access":    {urls: [...]}          <- todos os caminhos de acesso
    }
"""
from __future__ import annotations

import socket
from typing import Any, Dict, List

from ..config import config
from ..logging_setup import get
from . import connectivity, nm, tailscale

log = get("network")


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "pregacao-pi"


def _urls(eth: Dict[str, Any], wifi: Dict[str, Any], ap: Dict[str, Any],
          ts: Dict[str, Any]) -> List[Dict[str, str]]:
    """Todos os enderecos pelos quais o painel pode ser aberto."""
    port = config.port
    host = _hostname()
    items: List[Dict[str, str]] = []

    items.append({
        "id": "mdns",
        "label": "Local (nome)",
        "value": f"http://{host}.local:{port}",
        "note": "mesma rede Wi-Fi/Ethernet",
        "available": True,
    })
    if eth.get("connected") and eth.get("ip"):
        items.append({
            "id": "ethernet",
            "label": "Ethernet",
            "value": f"http://{eth['ip']}:{port}",
            "note": "rede cabeada",
            "available": True,
        })
    if wifi.get("connected") and wifi.get("ip"):
        items.append({
            "id": "wifi",
            "label": "Wi-Fi",
            "value": f"http://{wifi['ip']}:{port}",
            "note": str(wifi.get("ssid") or ""),
            "available": True,
        })
    if ap.get("active"):
        items.append({
            "id": "ap",
            "label": "Access Point",
            "value": f"http://{ap['ip']}:{port}",
            "note": str(ap.get("ssid") or ""),
            "available": True,
        })
    if ts.get("connected") and ts.get("ip"):
        items.append({
            "id": "tailscale",
            "label": "Acesso remoto",
            "value": f"http://{ts['ip']}:{port}",
            "note": "rede privada Tailscale",
            "available": True,
        })
    return items


def build(with_internet: bool = True, timeout: float = 4.0) -> Dict[str, Any]:
    """Monta o status completo. Nunca lanca excecao para a interface."""
    try:
        eth = nm.ethernet_status()
    except Exception as exc:  # pragma: no cover - defesa de UI
        log.warning("[NETWORK] falha ao ler Ethernet: %s", exc)
        eth = {"available": False, "connected": False, "ip": "", "gateway": "",
               "state": "indisponivel"}

    try:
        wifi = nm.wifi_status()
    except Exception as exc:  # pragma: no cover - defesa de UI
        log.warning("[NETWORK] falha ao ler Wi-Fi: %s", exc)
        wifi = {"available": False, "connected": False, "ssid": "", "ip": "",
                "gateway": "", "signal": 0, "state": "indisponivel"}

    try:
        ap = nm.ap_status()
    except Exception as exc:  # pragma: no cover - defesa de UI
        log.warning("[NETWORK] falha ao ler Access Point: %s", exc)
        ap = {"active": False, "ssid": nm.ap_ssid(), "ip": nm.AP_GATEWAY,
              "state": "indisponivel"}

    internet = {"connected": False, "host": "", "port": 0, "latency_ms": 0}
    if with_internet:
        try:
            internet = connectivity.check(timeout=timeout)
        except Exception as exc:  # pragma: no cover - defesa de UI
            log.warning("[NETWORK] falha no teste de Internet: %s", exc)

    try:
        ts = tailscale.status()
    except Exception as exc:  # pragma: no cover - defesa de UI
        log.warning("[TAILSCALE] falha ao ler status: %s", exc)
        ts = {"installed": False, "connected": False, "ip": "", "message": str(exc)}

    local_network = bool(eth.get("connected") or wifi.get("connected")
                         or ap.get("active"))
    forced = bool(config.get("network.ap_forced", False))
    try:
        has_route = nm.has_default_route()
    except Exception:  # pragma: no cover - defesa de UI
        has_route = False

    return {
        "ethernet": eth,
        "wifi": wifi,
        "internet": internet,
        "accessPoint": {**ap, "forced": forced},
        "tailscale": ts,
        "online": bool(internet.get("connected")),
        "local": local_network,
        "has_route": has_route,
        "hostname": _hostname(),
        "access": {
            "hostname": _hostname(),
            "mdns": f"http://{_hostname()}.local:{config.port}",
            "port": config.port,
            "urls": _urls(eth, wifi, ap, ts),
        },
    }
