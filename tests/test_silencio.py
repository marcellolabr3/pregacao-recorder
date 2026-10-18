"""S1: silencio e housekeeping dos logs.

CREATE_NO_WINDOW e o que separa "roda em silencio" de "abre um console
a cada gravacao, listagem de dispositivo ou consulta de servico". Aqui
tambem ficam os testes da limpeza de handoff_*.log e da rotacao de
login_nlm.log, que antes cresciam sem teto nenhum.
"""
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import estudos
from app.api import routes
from app.audio import device
from app.recording import consolidate

FLAGS_ESPERADAS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


# ------------------------------------------------------- flags de janela
def test_flag_constante_compativel_com_a_plataforma():
    assert consolidate._FLAGS_SUBPROCESS == FLAGS_ESPERADAS
    assert device._FLAGS_SUBPROCESS == FLAGS_ESPERADAS
    assert routes._FLAGS_SUBPROCESS == FLAGS_ESPERADAS


def test_consolidate_ffmpeg_chama_com_flag_de_janela(tmp_path, monkeypatch):
    segmentos = []
    for indice in range(2):
        seg = tmp_path / f"segment_{indice:04d}.wav"
        seg.write_bytes(b"\x00" * 512)
        segmentos.append(seg)

    chamada = {}

    def _fake_run(cmd, **kwargs):
        chamada.update(kwargs)
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(consolidate, "has_ffmpeg", lambda: True)
    monkeypatch.setattr(consolidate.subprocess, "run", _fake_run)

    final = tmp_path / "saida.mp3"
    with pytest.raises(RuntimeError, match="ffmpeg falhou"):
        consolidate.consolidate(segmentos, final, 44100, 1)
    # mesmo na falha, a chamada saiu sem janela visivel
    assert chamada["creationflags"] == FLAGS_ESPERADAS


def test_device_run_chama_com_flag_de_janela(monkeypatch):
    chamada = {}

    def _fake_run(cmd, **kwargs):
        chamada.update(kwargs)
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(device.subprocess, "run", _fake_run)
    device._run(["ffmpeg", "-version"], timeout=5)
    assert chamada["creationflags"] == FLAGS_ESPERADAS


def test_capture_level_chama_com_flag_de_janela(monkeypatch):
    monkeypatch.setattr(
        device.shutil,
        "which",
        lambda n: f"/ffmpeg/bin/{n}" if n == "ffmpeg" else None,
    )
    chamada = {}

    def _fake_run(cmd, **kwargs):
        chamada.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"\x00\x10" * 4410, stderr=b"")

    monkeypatch.setattr(device.subprocess, "run", _fake_run)
    out = device.capture_level(1.0, "Microfone (Fake)")
    assert out["ok"] is True
    assert chamada["creationflags"] == FLAGS_ESPERADAS


def test_service_state_chama_com_flag_de_janela(monkeypatch):
    chamada = {}

    def _fake_run(cmd, **kwargs):
        chamada.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="active\n", stderr="")

    monkeypatch.setattr(routes.subprocess, "run", _fake_run)
    assert routes._service_state("pregacao") == "active"
    assert chamada["creationflags"] == FLAGS_ESPERADAS


# ------------------------------------------------- housekeeping dos logs
def _aponta_pasta(monkeypatch, tmp_path: Path) -> Path:
    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        estudos, "_cfg", lambda chave: str(tmp_path) if chave == "pasta" else ""
    )
    return logs


def test_limpar_logs_antigos_mantem_so_os_mais_novos(monkeypatch, tmp_path):
    logs = _aponta_pasta(monkeypatch, tmp_path)
    for dia in range(40):
        (logs / f"handoff_{dia:02d}_120000.log").write_text("x", encoding="utf-8")

    estudos._limpar_logs_antigos(manter=30)

    sobrou = sorted(p.name for p in logs.glob("handoff_*.log"))
    assert len(sobrou) == 30
    # os 10 mais antigos sumiram; o mais novo continua
    assert "handoff_00_120000.log" not in sobrou
    assert "handoff_39_120000.log" in sobrou


def test_limpar_logs_antigos_nao_toca_nos_estudos_recentes(monkeypatch, tmp_path):
    logs = _aponta_pasta(monkeypatch, tmp_path)
    for dia in range(5):
        (logs / f"handoff_{dia:02d}_120000.log").write_text("x", encoding="utf-8")

    estudos._limpar_logs_antigos(manter=30)

    assert len(list(logs.glob("handoff_*.log"))) == 5


def test_limpar_logs_antigos_rotaciona_login_nlm_grande(monkeypatch, tmp_path):
    logs = _aponta_pasta(monkeypatch, tmp_path)
    login = logs / "login_nlm.log"
    login.write_bytes(b"a" * (2 * 1024 * 1024 + 1))

    estudos._limpar_logs_antigos()

    assert not login.exists()
    velho = logs / "login_nlm.log.1"
    assert velho.exists()
    assert velho.stat().st_size > 2 * 1024 * 1024


def test_limpar_logs_antigos_nao_reclama_sem_logs(monkeypatch, tmp_path):
    # pasta de logs nem criada ainda: a rotina nao pode derrubar o vigia
    monkeypatch.setattr(
        estudos, "_cfg", lambda chave: str(tmp_path) if chave == "pasta" else ""
    )
    estudos._limpar_logs_antigos()
