"""Teste de conectividade com a Internet.

Regra do projeto: a Internet pode cair sem derrubar o sistema. Este modulo
responde APENAS a pergunta "ha saida para a Internet?" -- o acesso local ao
painel nao depende do resultado.

A checagem e TCP puro (sem DNS quando o alvo e IP, sem HTTP) para ser rapida
e nao gerar trafego relevante.
"""
from __future__ import annotations

import socket
import time
from typing import Any, Dict, List, Optional

from ..config import config
from ..logging_setup import get

log = get("network")

FALLBACK_TARGETS = [("1.1.1.1", 443), ("8.8.8.8", 53)]


def _probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def targets() -> List[tuple]:
    host = str(config.get("network.check_host", "www.googleapis.com"))
    port = int(config.get("network.check_port", 443))
    ordered = [(host, port)]
    for item in FALLBACK_TARGETS:
        if item not in ordered:
            ordered.append(item)
    return ordered


def check(timeout: float = 4.0) -> Dict[str, Any]:
    """Tenta alguns destinos; devolve o primeiro que responde."""
    started = time.monotonic()
    for host, port in targets():
        if _probe(host, port, timeout):
            latency = int((time.monotonic() - started) * 1000)
            return {
                "connected": True,
                "host": host,
                "port": port,
                "latency_ms": latency,
            }
    return {
        "connected": False,
        "host": "",
        "port": 0,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def available(timeout: Optional[float] = None) -> bool:
    """Conveniencia: apenas True/False."""
    return bool(check(timeout or 4.0)["connected"])
