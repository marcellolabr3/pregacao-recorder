"""Configuracao persistente: defaults + config.json + variaveis de ambiente."""
from __future__ import annotations

import copy
import json
import os
import re
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from . import paths

#: identificador do aparelho: so entra no topic MQTT o que for seguro
DEVICE_ID_RE = re.compile(r"[^0-9A-Za-z_-]+")


def sanitize_device_id(value: str) -> str:
    """Reduz um identificador a ``[A-Za-z0-9_-]`` (seguro em topic MQTT).

    ``#`` e ``+``, por exemplo, sao curingas de topic e seriam interpretados
    pelo broker; nunca podem aparecer num device_id.
    """
    cleaned = DEVICE_ID_RE.sub("-", str(value or "").strip()).strip("-_")
    return cleaned[:32] or "pregacao"


def _generated_device_id() -> str:
    """Identificador estavel do PC a partir do hostname."""
    host = socket.gethostname().strip()
    if host and host.lower() != "localhost":
        return sanitize_device_id(host)
    return "pregacao-local"


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_env(path: Optional[Path] = None) -> Dict[str, str]:
    """Carrega um arquivo .env simples (KEY=VALUE) sem sobrescrever o ambiente."""
    env_path = path or paths.env_file()
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
        os.environ.setdefault(key, value)
    return values


class Config:
    """Acesso unificado a configuracao. Todas as leituras passam por aqui."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base = Path(base_dir) if base_dir else paths.home()
        self._lock = threading.RLock()
        self._defaults: Dict[str, Any] = {}
        self._values: Dict[str, Any] = {}
        self.reload()

    # ------------------------------------------------------------------
    @property
    def defaults_file(self) -> Path:
        return self._base / "config" / "default.json"

    @property
    def user_file(self) -> Path:
        return self._base / "config" / "config.json"

    def reload(self) -> None:
        with self._lock:
            self._defaults = {}
            if self.defaults_file.exists():
                self._defaults = json.loads(self.defaults_file.read_text(encoding="utf-8"))
            user: Dict[str, Any] = {}
            if self.user_file.exists():
                try:
                    user = json.loads(self.user_file.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    user = {}
            self._values = _deep_merge(self._defaults, user)
            # Chaves de AP/Wi-Fi antigas nao voltam a aparecer na API nem sao usadas.
            network = self._values.get("network", {})
            if isinstance(network, dict):
                self._values["network"] = {k: v for k, v in network.items()
                                           if k in ("check_host", "check_port", "retry_seconds")}

    # ------------------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._values
            for part in dotted.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        with self._lock:
            node = self._values
            for part in parts[:-1]:
                nxt = node.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    node[part] = nxt
                node = nxt
            node[parts[-1]] = value

    def as_dict(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._values)

    def save(self) -> None:
        with self._lock:
            self.user_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.user_file.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self._values, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.user_file)

    # -- atalhos ---------------------------------------------------------
    @property
    def device_id(self) -> str:
        """Identificador unico deste aparelho (topics MQTT, APK, painel).

        Ordem de precedencia: ``PREGACAO_DEVICE_ID`` (`.env`) -> ``device_id``
        do config.json (CONFIGURACOES AVANCADAS) -> valor gerado a partir do
        hostname. O resultado e sempre sanitizado para ``[A-Za-z0-9_-]``.
        """
        raw = (
            os.environ.get("PREGACAO_DEVICE_ID", "").strip()
            or str(self.get("device_id", "") or "").strip()
        )
        return sanitize_device_id(raw) if raw else _generated_device_id()

    @property
    def recordings_root(self) -> Path:
        configured = str(self.get("storage.recordings_dir") or "").strip()
        if configured:
            return Path(configured)
        return paths.recordings_dir()

    @property
    def pin(self) -> str:
        return os.environ.get("PREGACAO_PIN", "").strip()

    @property
    def secret(self) -> str:
        secret = os.environ.get("PREGACAO_SECRET", "").strip()
        return secret or "pregacao-recorder-DEV-SECRET-troque-em-producao"

    @property
    def host(self) -> str:
        return os.environ.get("PREGACAO_HOST", "") or str(self.get("web.host", "0.0.0.0"))

    @property
    def port(self) -> int:
        raw = os.environ.get("PREGACAO_PORT", "").strip()
        try:
            return int(raw) if raw else int(self.get("web.port", 8080))
        except (TypeError, ValueError):
            return 8080

    @property
    def google_credentials_file(self) -> Path:
        raw = os.environ.get("GOOGLE_CREDENTIALS_FILE", "").strip()
        if raw:
            return Path(raw)
        return paths.config_dir() / "google_credentials.json"

    @property
    def google_token_file(self) -> Path:
        raw = os.environ.get("GOOGLE_TOKEN_FILE", "").strip()
        if raw:
            return Path(raw)
        return paths.config_dir() / "google_token.json"


config = Config()
