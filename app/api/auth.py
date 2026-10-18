"""Autenticacao simples por PIN (rede local da igreja).

O objetivo nao e expor o sistema a internet: e impedir que um toque acidental
de um visitante inicie ou finalize uma gravacao. Nao ha cadastro, nao ha
senha de terceiros, nao ha sessao persistente fora do cookie assinado.

Existem dois niveis:

* PIN normal  -> controlar gravacoes e ver o status;
* PIN de administrador (``PREGACAO_ADMIN_PIN``) -> CONFIGURACOES AVANCADAS
  (audio, armazenamento, credenciais OAuth, rede, logs).

Se ``PREGACAO_ADMIN_PIN`` nao estiver definido, o PIN normal tambem abre a
area avancada (instalacao simples).
"""
from __future__ import annotations

import functools
import hmac
import os
from typing import Any, Callable, Dict

from flask import Response, jsonify, request, session

from ..config import config


def pin_configured() -> bool:
    return len(config.pin) >= 4


def is_authenticated() -> bool:
    if not pin_configured():
        return True
    return bool(session.get("auth"))


def check_pin(pin: str) -> bool:
    if not pin_configured():
        return True
    return hmac.compare_digest(str(pin or ""), config.pin)


def login(pin: str) -> bool:
    if not check_pin(pin):
        return False
    session.clear()
    session["auth"] = True
    session.permanent = True
    return True


def logout() -> None:
    session.clear()


# ---------------------------------------------------------------- admin
def admin_pin() -> str:
    """PIN das CONFIGURACOES AVANCADAS (cai para o PIN normal se nao definido)."""
    return (os.environ.get("PREGACAO_ADMIN_PIN", "") or "").strip() or config.pin


def admin_configured() -> bool:
    return len(admin_pin()) >= 4


def is_admin() -> bool:
    if not admin_configured():
        return True
    if not is_authenticated():
        return False
    return bool(session.get("admin"))


def admin_login(pin: str) -> bool:
    if not admin_configured():
        session["admin"] = True
        return True
    if not hmac.compare_digest(str(pin or ""), admin_pin()):
        return False
    session["admin"] = True
    session.permanent = True
    return True


def require_admin(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        if not is_authenticated():
            return jsonify({"error": "nao_autenticado", "message": "PIN obrigatorio"}), 401
        if not is_admin():
            return (
                jsonify(
                    {
                        "error": "admin_obrigatorio",
                        "message": "PIN de administrador necessario "
                        "(CONFIGURACOES AVANCADAS)",
                    }
                ),
                403,
            )
        return view(*args, **kwargs)

    return wrapper


def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        if not is_authenticated():
            return jsonify({"error": "nao_autenticado", "message": "PIN obrigatorio"}), 401
        return view(*args, **kwargs)

    return wrapper


def unauthorized(message: str = "PIN obrigatorio") -> Response:
    return jsonify({"error": "nao_autenticado", "message": message}), 401


def session_info() -> Dict[str, Any]:
    return {
        "auth": is_authenticated(),
        "pin_required": pin_configured(),
        "admin": is_admin(),
        "admin_pin_required": admin_configured() and not is_admin(),
        "remote": request.remote_addr,
    }
