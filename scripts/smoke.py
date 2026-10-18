"""Smoke test do servidor em execucao (localhost).
Uso: python scripts/smoke.py [url] [pin] [pin_admin]
"""
import json
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"
PIN = sys.argv[2] if len(sys.argv) > 2 else "4821"

jar = CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with op.open(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


checks = []


def check(label, ok, extra=""):
    checks.append((label, ok, extra))
    print(f"  [{'OK' if ok else 'XX'}] {label} {extra}")


print("smoke test -", BASE)

# O painel pode operar sem PIN (PREGACAO_PIN vazio). Nesse caso as checagens
# de bloqueio nao existem e - mais importante - um POST /api/start sem PIN
# de fato INICIA UMA GRAVACAO, entao elas sao puladas em vez de rodadas.
s, d = call("GET", "/api/me")
PIN_ON = bool(d.get("pin_required"))
ADMIN_ON = bool(d.get("admin_pin_required"))
check("GET /api/me", s == 200 and d.get("auth") == (not PIN_ON), str(d))
print(f"  modo: PIN de acesso {'LIGADO' if PIN_ON else 'desativado'} | "
      f"PIN admin {'EXIGIDO' if ADMIN_ON else 'desativado'}")

s, d = call("GET", "/api/status")
check("GET /api/status publico", s == 200 and "state" in d)

if PIN_ON:
    s, d = call("POST", "/api/start")
    check("start bloqueado sem PIN (401)", s == 401)

    s, d = call("POST", "/api/login", {"pin": "0000"})
    check("PIN errado rejeitado (401)", s == 401)

    s, d = call("POST", "/api/login", {"pin": PIN})
    check("login correto", s == 200)
else:
    print("  [--] bloqueio por PIN nao testado (PIN desativado)")

s, d = call("POST", "/api/start")
# sem interface de audio (409) ou com audio real (200) - nos dois casos e valido
iniciada = s == 200
check("start: 409 sem audio ou 200 com audio", s in (200, 409),
      str(d.get("message")))
if iniciada:
    time.sleep(2.5)  # deixa o arecord escrever o primeiro segmento
    s1, d1 = call("POST", "/api/stop")
    check("stop da gravacao de teste -> 200", s1 == 200, str(d1.get("message")))

s, d = call("POST", "/api/stop")
check("stop sem gravacao -> 409", s == 409, str(d.get("message")))

# configuracao avancada exige o PIN de administrador
if ADMIN_ON:
    s, d = call("POST", "/api/config", {"audio.sample_rate": 12345})
    check("config avancada bloqueada sem admin (403)",
          s == 403 and d.get("error") == "admin_obrigatorio",
          str(d.get("message")))
else:
    print("  [--] bloqueio de administrador nao testado (PIN admin desativado)")

s, d = call("POST", "/api/config", {"device_name": "Smoke"})
check("config simples sem admin -> 200", s == 200, str(d.get("message")))

ADMIN_PIN = sys.argv[3] if len(sys.argv) > 3 else PIN
s, d = call("POST", "/api/admin/login", {"pin": ADMIN_PIN})
check("login de administrador", s == 200, str(d.get("message")))

s, d = call("POST", "/api/config", {"audio.sample_rate": 12345})
check("config invalida -> 422", s == 422, str(d.get("message")))

s, d = call("POST", "/api/config", {"audio.bitrate": 192, "device_name": "Smoke"})
check("config valida -> 200", s == 200 and "audio.bitrate" in d.get("applied", []))

s, d = call("GET", "/api/config")
check("GET /api/config", s == 200 and d["config"]["audio"]["bitrate"] == 192)

s, d = call("GET", "/api/audio/devices")
check("GET /api/audio/devices", s == 200 and "items" in d)

s, d = call("GET", "/api/recovery")
check("GET /api/recovery", s == 200 and d.get("items") == [])

s, d = call("POST", "/api/recovery/nao-existe/recover")
check("recuperacao inexistente -> 409", s == 409)

s, d = call("GET", "/api/drive/status")
check("GET /api/drive/status", s == 200 and "connected" in d)

s, d = call("POST", "/api/uploads/retry")
check("retry da fila de uploads", s == 200)

s, d = call("GET", "/api/events/history")
check("notificacoes persistidas", s == 200 and len(d.get("items", [])) > 0)

s, d = call("GET", "/api/ping")
check("healthcheck", s == 200)

fails = [c for c in checks if not c[1]]
print(f"\n{len(checks) - len(fails)}/{len(checks)} verificacoes ok")
sys.exit(1 if fails else 0)
