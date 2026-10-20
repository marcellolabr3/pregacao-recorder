"""Contrato do reenvio e do estado de sessao, sem contato com WhatsApp real."""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import whatsapp
from app.config import config


def test_multiplos_numeros_legados_e_validacao():
    assert whatsapp.parse_numbers("+5511999999999\n5511888888888,5511999999999") == [
        "5511999999999", "5511888888888"
    ]
    with pytest.raises(ValueError):
        whatsapp.parse_numbers("5511999999999,5511x8888888")


def test_sessao_salva_nao_e_conexao_verificada(monkeypatch, tmp_path):
    pipeline = tmp_path / "pipeline"
    (pipeline / "whatsapp").mkdir(parents=True)
    (pipeline / "whatsapp" / "send.js").write_text("// simulado")
    config.set("estudos.pasta", str(pipeline))
    config.set("estudos.whatsapp", "5511999999999")
    monkeypatch.setenv("PREGACAO_PIPELINE_HOME", str(pipeline))
    monkeypatch.setitem(whatsapp._state, "result", "")
    assert whatsapp.status()["connection"] == "login_necessario"
    (pipeline / "whatsapp" / "auth").mkdir()
    (pipeline / "whatsapp" / "auth" / "creds.json").write_text("{}")
    assert whatsapp.status()["connection"] == "sessao_salva_nao_verificada"


def test_reenvio_usa_pdf_existente_sem_regenerar(monkeypatch, tmp_path, database):
    pipeline = tmp_path / "pipeline"
    output = pipeline / "output"
    output.mkdir(parents=True)
    (pipeline / "whatsapp").mkdir()
    (pipeline / "whatsapp" / "send.js").write_text("// simulado")
    pdf = output / "estudo.pdf"
    pdf.write_bytes(b"%PDF-simulado")
    config.set("estudos.pasta", str(pipeline))
    monkeypatch.setenv("PREGACAO_PIPELINE_HOME", str(pipeline))
    monkeypatch.setattr(whatsapp, "db", database)
    monkeypatch.setattr(whatsapp, "_node", lambda: "node-simulado")
    assert database.create_job(str(tmp_path / "audio.mp3"))
    job = database.claim_job()
    assert job is not None
    database.save_study_artifact(job["job_id"], pdf_path=str(pdf))
    database.job_concluir(job["job_id"], etapa="FINAL_INCERTO")
    called = []

    def fake_command(*args, **kwargs):
        called.append(args)
        return SimpleNamespace(returncode=0, stdout="ACEITO:msg-123\n", stderr="")

    monkeypatch.setattr(whatsapp, "_command", fake_command)
    ids = whatsapp.resend(job["job_id"], "5511999999999,5511888888888")
    end = time.time() + 3
    while time.time() < end and any(
        item["status"] == "PENDENTE" for item in database.list_whatsapp_sends(job["job_id"])
    ):
        time.sleep(0.01)
    sends = database.list_whatsapp_sends(job["job_id"])
    assert len(ids) == len(sends) == len(called) == 2
    assert all(item["status"] == "ACEITO_PELO_SERVIDOR" for item in sends)
    assert all(args[1] == str(pdf) for args in called)
    assert database.get_job(job["job_id"])["estado"] == "CONCLUIDO"
