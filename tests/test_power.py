"""Desligamento so depois das filas: comando Windows sempre simulado."""
from __future__ import annotations

from types import SimpleNamespace

from app import power
from app.config import config


def test_contagem_so_comeca_depois_da_atividade_e_reinicia(monkeypatch):
    controller = power.ShutdownController()
    config.set("power.shutdown_after_tasks", True)
    config.set("power.shutdown_delay_minutes", 2)
    busy = []
    monkeypatch.setattr(controller, "busy_reasons", lambda: busy[:])
    calls = []
    monkeypatch.setattr(power.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))

    assert controller.tick(1000)["state"] == "aguardando_atividade"
    busy.append("gravacao")
    assert controller.tick(1001)["state"] == "aguardando_tarefas"
    busy.clear()
    assert controller.tick(1002)["deadline"] == 1122
    assert controller.tick(1050)["state"] == "contagem"
    busy.append("upload")
    assert controller.tick(1060)["deadline"] is None
    busy.clear()
    assert controller.tick(1061)["deadline"] == 1181
    assert calls == []
    controller.tick(1181)
    if power.os.name == "nt":
        assert calls == [["shutdown.exe", "/s", "/t", "0"]]
    else:
        assert calls == []


def test_cancelamento_nao_desliga_ate_nova_tarefa(monkeypatch):
    controller = power.ShutdownController()
    config.set("power.shutdown_after_tasks", True)
    config.set("power.shutdown_delay_minutes", 1)
    monkeypatch.setattr(controller, "busy_reasons", lambda: [])
    calls = []
    monkeypatch.setattr(power.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    controller.arm()
    assert controller.status()["state"] == "contagem"
    assert controller.cancel()["state"] == "aguardando_atividade"
    controller.tick(9999999999)
    assert calls == []


def test_filas_e_recuperacao_bloqueiam_contagem(monkeypatch, database, fresh_state):
    from app.states import State, state_machine
    controller = power.ShutdownController()
    monkeypatch.setattr(power, "db", database)
    assert controller.busy_reasons() == []
    state_machine.set(State.RECORDING, force=True)
    assert "gravacao/finalizacao" in controller.busy_reasons()
    state_machine.set(State.IDLE, force=True)
    database.create_job("audio.mp3")
    assert "estudos pendentes" in controller.busy_reasons()
    database.record_whatsapp_send("job", "5511999999999", "PENDENTE")
    assert "reenvios WhatsApp pendentes" in controller.busy_reasons()
