"""Encerramento do capturador (SegmentRecorder.stop).

Regressao: ``send_signal(signal.SIGINT)`` lanca ``ValueError`` no Windows
(sistemas sem SIGINT generico) - o FINALIZAR devolvia HTTP 500. O correto
e cair para ``terminate()`` sem derrubar a finalizacao.
"""
import subprocess
import sys
from pathlib import Path

from app.audio.recorder import SegmentRecorder


def _spawn_sleep() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )


def test_stop_terminates_process_without_raising(tmp_path: Path):
    rec = SegmentRecorder(session_dir=tmp_path, device="hw:1,0")
    proc = _spawn_sleep()
    rec._proc = proc
    try:
        rec.stop(timeout=5)          # nao pode lancar excecao em SO nenhum
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.poll() is not None, "processo de captura deveria ter encerrado"


def test_stop_without_process_is_safe(tmp_path: Path):
    rec = SegmentRecorder(session_dir=tmp_path, device="hw:1,0")
    rec.stop(timeout=1)              # sem processo: nada a encerrar


# ------------------------------------------------- selecao de backend
def _which_stub(presentes):
    return lambda nome: f"/usr/bin/{nome}" if nome in presentes else None


def test_comando_prefere_arecord_quando_existe(tmp_path: Path, monkeypatch):
    from app.audio import recorder as rec_mod

    monkeypatch.setattr(rec_mod.shutil, "which", _which_stub({"arecord", "ffmpeg"}))
    rec = SegmentRecorder(session_dir=tmp_path, device="hw:1,0")
    cmd = rec._comando_captura()
    assert cmd[0] == "arecord"


def test_comando_usa_ffmpeg_dshow_quando_so_tem_ffmpeg(tmp_path: Path, monkeypatch):
    from app.audio import recorder as rec_mod

    monkeypatch.setattr(rec_mod.shutil, "which", _which_stub({"ffmpeg"}))
    rec = SegmentRecorder(session_dir=tmp_path, device="Microfone (X)")
    cmd = rec._comando_captura()
    assert cmd[0] == "ffmpeg"
    assert "dshow" in cmd
    assert "audio=Microfone (X)" in cmd
    assert "pipe:1" in cmd


def test_spawn_sem_ferramenta_define_erro_instalacao(tmp_path: Path, monkeypatch):
    from app.audio import recorder as rec_mod

    monkeypatch.setattr(rec_mod.shutil, "which", _which_stub(set()))
    rec = SegmentRecorder(session_dir=tmp_path, device="default")
    assert rec._comando_captura() is None
    assert rec._spawn() is None
    assert "ffmpeg" in rec.error  # orienta a instalacao no Windows


# ------------------------------------------------- trava de instancia unica
def test_trava_impede_segunda_instancia(tmp_path: Path):
    import os

    from app.remote.agent import TravaInstancia

    caminho = tmp_path / "agente.pid"
    primeira = TravaInstancia(caminho)
    assert primeira.adquirir() is True
    assert caminho.read_text().strip() == str(os.getpid())

    segunda = TravaInstancia(caminho)
    assert segunda.adquirir() is False  # o pid atual esta vivo

    primeira.liberar()
    assert not caminho.exists()
    assert segunda.adquirir() is True  # liberada, agora sim


def test_trava_assume_pid_morto(tmp_path: Path):
    import os
    import subprocess
    import sys

    from app.remote.agent import TravaInstancia

    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    caminho = tmp_path / "agente.pid"
    caminho.write_text(str(proc.pid))

    trava = TravaInstancia(caminho)
    assert trava.adquirir() is True  # dono anterior ja morreu
    assert caminho.read_text().strip() == str(os.getpid())


def test_trava_arquivo_corrompido_nao_bloqueia(tmp_path: Path):
    from app.remote.agent import TravaInstancia

    caminho = tmp_path / "agente.pid"
    caminho.write_text("nao-e-pid")

    assert TravaInstancia(caminho).adquirir() is True


def test_detect_cached_so_executa_uma_vez(monkeypatch):
    from app.audio import device

    device._cache_limpa()
    chamadas = {"n": 0}

    def fake_detect(configured="auto"):
        chamadas["n"] += 1
        return {"hw": "Hw X", "name": "X", "usb": False}

    monkeypatch.setattr(device, "detect", fake_detect)
    a = device.detect_cached("auto")
    b = device.detect_cached("auto")
    assert a == b == {"hw": "Hw X", "name": "X", "usb": False}
    assert chamadas["n"] == 1  # o painel nao pode abrir processo a cada poll
    device._cache_limpa()
