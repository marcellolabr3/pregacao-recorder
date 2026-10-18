"""Teste E2E REAL de gravacao contra um servidor pregacao-recorder no ar.

Requer um `arecord` no PATH (no Windows: scripts/devtools/bin/arecord.exe,
o simulador que emite PCM real). Cobre:

  1. login + interface de audio detectada
  2. teste de sinal (dBFS)
  3. INICIAR -> RECORDING com bytes crescendo
  4. FINALIZAR -> arquivo unico salvo (ffmpeg -> MP3)
  5. historico/sessao com o arquivo final
  6. fila de upload pendente preservada (Drive nao conectado)

Uso:  python scripts/devtools/e2e_test.py http://127.0.0.1:8099 <pin>
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
PIN = sys.argv[2] if len(sys.argv) > 2 else "4821"

_jar = urllib.request.HTTPCookieProcessor()
_op = urllib.request.build_opener(_jar)
PASS, FAIL = [], []


def api(path: str, method: str = "GET", body=None, timeout: float = 20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    with _op.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(name)
    print(f"[{'OK  ' if ok else 'FALHA'}] {name}" + (f" - {detail}" if detail else ""))
    return ok


# 1. login ---------------------------------------------------------------
try:
    api("/api/login", "POST", {"pin": PIN})
    check("login com PIN", True)
except urllib.error.HTTPError as exc:
    check("login com PIN", False, f"HTTP {exc.code}")
    sys.exit(1)

st = api("/api/status")
devs = st.get("audio_devices") or []
check("interface de audio detectada", bool(devs),
      json.dumps(devs[:2], ensure_ascii=False))

# 2. teste de sinal ------------------------------------------------------
audio = api("/api/audio/test", "POST")
check("teste de sinal devolve dBFS", bool(audio.get("ok")),
      f"pico={audio.get('peak_db')} silent={audio.get('silent')}")

# 3. INICIAR -------------------------------------------------------------
try:
    r = api("/api/start", "POST")
    check("INICIAR gravacao", r.get("state") == "RECORDING", str(r.get("state")))
except urllib.error.HTTPError as exc:
    check("INICIAR gravacao", False, f"HTTP {exc.code} {exc.read()[:200]}")
    sys.exit(1)

time.sleep(4)
st = api("/api/status")
rec = st.get("recording") or {}
check("estado GRAVANDO (RECORDING)", st.get("state") == "RECORDING", str(st.get("state")))
check("bytes sendo gravados", (rec.get("bytes") or 0) > 0, str(rec.get("bytes")))
check("segmento em disco", (rec.get("segments") or 0) >= 1, str(rec.get("segments")))

# segunda gravacao deve ser recusada
try:
    api("/api/start", "POST")
    check("segunda gravacao recusada", False, "aceitou gravar em cima")
except urllib.error.HTTPError as exc:
    check("segunda gravacao recusada", exc.code == 409, f"HTTP {exc.code}")

# 4. FINALIZAR -----------------------------------------------------------
r = api("/api/stop", "POST")
check("FINALIZAR aceito", r.get("ok") is True, str(r.get("state")))

fim = None
for _ in range(40):
    st = api("/api/status")
    if st.get("state") in ("COMPLETED", "IDLE", "UPLOADING", "ERROR"):
        fim = st.get("state")
        break
    time.sleep(1)
check("finalizacao concluiu", fim in ("COMPLETED", "IDLE", "UPLOADING"), str(fim))

# 5. arquivo final no historico -----------------------------------------
hist = api("/api/recordings")
sess = (hist.get("sessions") or [{}])[0]
final = sess.get("final_path") or ""
check("arquivo final criado (MP3/WAV)", bool(final), final)
check("arquivo com tamanho real", (sess.get("final_bytes") or 0) > 30000,
      str(sess.get("final_bytes")))
check("sessao marcada como concluida", sess.get("state") == "COMPLETED",
      str(sess.get("state")))

# 6. fila de upload preservada (Drive nao conectado) ----------------------
ups = st.get("uploads") or {}
check("fila de upload registrada", "pending" in ups, json.dumps(ups))
retry = api("/api/uploads/retry", "POST")
check("REENVIAR FILA funciona", retry.get("ok", True) is not False,
      json.dumps(retry)[:120])

print()
print(f"RESULTADO: {len(PASS)} ok, {len(FAIL)} falha(s)")
if FAIL:
    print("falharam: " + ", ".join(FAIL))
sys.exit(1 if FAIL else 0)
