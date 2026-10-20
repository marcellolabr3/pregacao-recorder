"""Preferencias MQTT locais; o painel nunca precisa reescrever o .env."""
from __future__ import annotations

import ipaddress
import re
from typing import Any, Mapping

from ..config import sanitize_device_id


ENV_KEYS = {
    "enabled": "PREGACAO_REMOTE_ENABLED",
    "host": "PREGACAO_REMOTE_HOST",
    "port": "PREGACAO_REMOTE_PORT",
    "tls": "PREGACAO_REMOTE_TLS",
    "username": "PREGACAO_REMOTE_USERNAME",
    "password": "PREGACAO_REMOTE_PASSWORD",
    "device_id": "PREGACAO_DEVICE_ID",
    "operator_token": "PREGACAO_OPERATOR_TOKEN",
}


def effective_environment(cfg: Any, environ: Mapping[str, str]) -> dict[str, str]:
    """A escolha salva pelo administrador prevalece sobre o .env legado.

    Sem bloco ``remote`` o comportamento anterior fica integralmente preservado.
    Nao modifica o ambiente recebido nem publica segredos em logs.
    """
    env = dict(environ)
    saved = cfg.get("remote", {})
    if isinstance(saved, dict):
        for key, name in ENV_KEYS.items():
            if key in saved:
                value = saved[key]
                env[name] = ("1" if value else "0") if isinstance(value, bool) else str(value)
    return env


def _text(value: Any, key: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"valor invalido para {key}")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"caracteres invalidos em {key}")
    return value


def _valid_host(host: str) -> bool:
    if not host or len(host) > 253:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?", host
        ))


def validate_update(body: Any, current: Any) -> dict[str, Any]:
    """Valida todo o pedido antes de persistir; campos secretos vazios preservam.

    Topics sao derivados do ID; nao podem ser informados pelo cliente nem conter
    curingas, barras ou um prefixo diferente do protocolo existente do APK.
    """
    if not isinstance(body, dict) or not body:
        raise ValueError("informe a configuracao MQTT")
    if set(body) - set(ENV_KEYS):
        raise ValueError("campo MQTT desconhecido")
    result = {
        "enabled": not current.disabled,
        "host": current.host,
        "port": current.port,
        "tls": current.tls,
        "username": current.username,
        "password": current.password,
        "device_id": current.device_id,
        "operator_token": current.operator_token,
    }
    for key, value in body.items():
        if key in ("enabled", "tls"):
            if not isinstance(value, bool):
                raise ValueError(f"{key} deve ser verdadeiro ou falso")
        elif key == "port":
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
                raise ValueError("porta MQTT deve estar entre 1 e 65535")
        else:
            value = _text(value, key)
            if key != "password":
                value = value.strip()
            if key in ("password", "operator_token") and not value:
                continue
        result[key] = value
    if not 1 <= result["port"] <= 65535:
        raise ValueError("porta MQTT deve estar entre 1 e 65535")
    if result["host"] and not _valid_host(result["host"]):
        raise ValueError("host MQTT invalido: use somente o nome ou IP, sem protocolo, porta ou caminho")
    if result["enabled"] and not result["host"]:
        raise ValueError("informe o host para habilitar o controle remoto")
    device_id = result["device_id"]
    if not device_id or len(device_id) > 32 or sanitize_device_id(device_id) != device_id:
        raise ValueError("ID MQTT invalido: use ate 32 letras, numeros, '_' ou '-', com letra ou numero nas extremidades")
    # A porta 8883 nao obriga TLS e a 1883 nao o proibe: brokers podem usar
    # portas personalizadas. O campo TLS e booleano e mantem a verificacao CA.
    return result
