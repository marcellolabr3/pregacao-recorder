"""Parsing e selecao de dispositivos FFmpeg/DirectShow."""
from app.audio import device

# ------------------------------------------------------------------ dshow
# Windows (ffmpeg/DirectShow): saida real de `ffmpeg -list_devices true -f dshow`.
REAL_DSHOW = """
[dshow @ 0000026a1b2c3d40] DirectShow audio devices (some may be both video and audio devices)
[dshow @ 0000026a1b2c3d40]  "Microfone (Realtek(R) Audio)"
[dshow @ 0000026a1b2c3d40]     Alternative name "@device_cm_{33D9A762-91C4-11DB-B2A6-0040D6165FE8}_wave#0_0"
[dshow @ 0000026a1b2c3d40]  "USB PnP Sound Device (0)"
[dshow @ 0000026a1b2c3d40]     Alternative name "@device_cm_{33D9A762-91C4-11DB-B2A6-0040D6165FE8}_wave#1_0"
[dshow @ 0000026a1b2c3d40] DirectShow video devices (some may be both video and audio devices)
[dshow @ 0000026a1b2c3d40]  "USB Camera"
[dshow @ 0000026a1b2c3d40]     Alternative name "@device_cm_{33D9A762-91C4-11DB-B2A6-0040D6165FE8}_video#0_0"
"""


def _patch_dshow(monkeypatch, output):
    monkeypatch.setattr(
        device.shutil, "which", lambda n: f"/ffmpeg/bin/{n}" if n == "ffmpeg" else None
    )
    monkeypatch.setattr(device, "_run", lambda _cmd, timeout=10: output)


def test_list_devices_parses_dshow_output(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW)
    devs = device.list_devices()
    assert [d["hw"] for d in devs] == [
        "Microfone (Realtek(R) Audio)",
        "USB PnP Sound Device (0)",
    ]
    assert devs[1]["usb"] is True
    assert devs[0]["usb"] is False


def test_detect_dshow_prefers_usb(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW)
    det = device.detect("auto")
    assert det["hw"] == "USB PnP Sound Device (0)"
    assert det["selected_by"] == "auto-usb"


# Formato atual do ffmpeg (2026): marcador (audio)/(video) por linha, sem
# secao - regressao contra builds onde os cabecalhos clássicos nao existem.
REAL_DSHOW_ATUAL = """
[in#0 @ 000002312623e180] "Logi C270 HD WebCam" (video)
[in#0 @ 000002312623e180]   Alternative name "@device_pnp_\\\\?\\\\usb#vid_046d&pid_0825#global"
[in#0 @ 000002312623e180] "Microfone (Logi C270 HD WebCam)" (audio)
[in#0 @ 000002312623e180]   Alternative name "@device_cm_{33D9A762-90C8-11D0-BD43-00A0C911CE86}"
"""


def test_list_devices_parses_dshow_formato_atual(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW_ATUAL)
    devs = device.list_devices()
    assert [d["hw"] for d in devs] == ["Microfone (Logi C270 HD WebCam)"]
    assert devs[0]["card"] == -1


def test_detect_dshow_formato_atual(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW_ATUAL)
    det = device.detect("auto")
    assert det["hw"] == "Microfone (Logi C270 HD WebCam)"


def test_detect_dshow_configured_case_insensitive(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW)
    det = device.detect("usb pnp sound device (0)")
    assert det["hw"] == "USB PnP Sound Device (0)"
    assert det["selected_by"] == "config"


def test_capture_level_dshow_mede_rms(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW)

    class _Fake:
        returncode = 0
        stdout = b"\x00\x10" * 4410  # 0x1000 = 4096 de pico
        stderr = b""

    monkeypatch.setattr(device.subprocess, "run", lambda *a, **k: _Fake())
    out = device.capture_level(1.0, "USB PnP Sound Device (0)")
    assert out["ok"] is True
    assert out["peak"] == 4096
    assert out["silent"] is False


def test_capture_level_sem_backend_reporta_erro(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _n: None)
    out = device.capture_level(1.0)
    assert out["ok"] is False


def test_capture_level_uses_selected_sample_rate_and_channels(monkeypatch):
    _patch_dshow(monkeypatch, REAL_DSHOW)
    commands = []
    class _Fake:
        returncode = 0
        stdout = b"\x00\x10" * 100
        stderr = b""
    def capture(cmd, **kwargs):
        commands.append(cmd)
        return _Fake()
    monkeypatch.setattr(device.subprocess, "run", capture)
    result = device.capture_level(2.0, "USB PnP Sound Device (0)", sample_rate=48000, channels=2)
    assert result["ok"] is True
    assert commands[0][commands[0].index("-ar") + 1] == "48000"
    assert commands[0][commands[0].index("-ac") + 1] == "2"
    assert commands[0][commands[0].index("-i") + 1] == "audio=USB PnP Sound Device (0)"
