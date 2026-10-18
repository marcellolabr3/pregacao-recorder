"""S0: instancia unica do servidor.

Duas instancias dividiriam recuperacao, uploader e fila de estudos -
nenhuma etapa pode rodar duas vezes.
"""
from __future__ import annotations

import logging
import os
import sys
import types

import pytest

from app import main as main_mod
from app import paths


@pytest.fixture(autouse=True)
def _logging_restaurado():
    """_bootstrap() configura o logger 'pregacao' (propagate=False + nivel).

    Sem restaurar, os testes de rede que capturam logs via caplog (logger na
    raiz) falhariam depois dos testes deste arquivo.
    """
    from app import logging_setup

    alvo = logging.getLogger("pregacao")
    antes = (alvo.level, alvo.propagate, list(alvo.handlers), logging_setup._configured)
    yield
    alvo.setLevel(antes[0])
    alvo.propagate = antes[1]
    alvo.handlers[:] = antes[2]
    logging_setup._configured = antes[3]


def test_segunda_instancia_e_recusada_antes_de_construir(monkeypatch):
    pid = paths.home() / "logs" / "servidor.pid"
    pid.parent.mkdir(parents=True, exist_ok=True)
    pid.write_text(str(os.getpid()), encoding="utf-8")  # "outra" instancia viva
    construido = {"sim": False}

    def _build():
        construido["sim"] = True
        raise AssertionError("build nao pode rodar com a trava ocupada")

    monkeypatch.setattr(main_mod, "build", _build)
    assert main_mod.run(host="127.0.0.1", port=8099) is False
    assert construido["sim"] is False


def test_instancia_unica_adquire_a_trava_e_sobe(monkeypatch):
    monkeypatch.setattr(main_mod, "build", lambda: (None, None, None))
    monkeypatch.setattr(main_mod, "_install_signal_handlers", lambda *a: None)
    # limpa a trava que o teste anterior deixou com um pid vivo
    pid = paths.home() / "logs" / "servidor.pid"
    if pid.exists():
        pid.unlink()

    class _Servidor(Exception):
        pass

    def _serve(*_args, **_kwargs):
        raise _Servidor("servidor de teste chamado")

    # run() importa `from waitress import serve` no momento do uso
    monkeypatch.setitem(sys.modules, "waitress", types.SimpleNamespace(serve=_serve))

    try:
        main_mod.run(host="127.0.0.1", port=8099)
        raise AssertionError("serve() deveria ter sido chamado")
    except _Servidor:
        pass

    pid = paths.home() / "logs" / "servidor.pid"
    assert pid.read_text(encoding="utf-8").strip() == str(os.getpid())
