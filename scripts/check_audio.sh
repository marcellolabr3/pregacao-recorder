#!/usr/bin/env bash
# Verifica se o Raspberry esta realmente capturando audio da mesa.
# Uso: ./scripts/check_audio.sh  [segundos]
set -euo pipefail

SECONDS_TO_CAPTURE="${1:-3}"

echo "=== interfaces de audio ALSA ==="
arecord -l || true
echo

echo "=== dispositivos padrao ==="
cat /proc/asound/cards 2>/dev/null || echo "(nenhum)"
echo

# Escolhe a primeira placa USB, se existir.
CARD="$(arecord -l 2>/dev/null | grep -i usb | head -n1 | sed -E 's/^card ([0-9]+):.*/\1/' || true)"
if [[ -z "${CARD}" ]]; then
  CARD="$(arecord -l 2>/dev/null | sed -nE 's/^card ([0-9]+):.*/\1/p' | head -n1 || true)"
fi

if [[ -z "${CARD}" ]]; then
  echo "NENHUMA interface de audio encontrada."
  echo " -> Confira o cabo USB e rode: lsusb"
  exit 1
fi

DEV="hw:${CARD},0"
echo "=== capturando ${SECONDS_TO_CAPTURE}s em ${DEV} ==="
TMP="$(mktemp /tmp/audio-XXXXXX.raw)"
trap 'rm -f "${TMP}"' EXIT

arecord -q -D "${DEV}" -f S16_LE -r 44100 -c 1 -d "${SECONDS_TO_CAPTURE}" -t raw "${TMP}"

SIZE=$(stat -c%s "${TMP}")
echo "bytes capturados: ${SIZE}"

if [[ "${SIZE}" -eq 0 ]]; then
  echo "FALHA: nenhum byte capturado."
  exit 1
fi

# Calcula pico (amostras de 16 bits little-endian) em 100% bash e desnecessario:
# usamos python3 quando disponivel.
if command -v python3 >/dev/null 2>&1; then
  python3 - "$TMP" <<'PY'
import struct, sys, math
raw = open(sys.argv[1], "rb").read()
samples = [struct.unpack_from("<h", raw, i)[0] for i in range(0, len(raw) - 1, 2)]
peak = max((abs(s) for s in samples), default=0)
rms = int((sum(s * s for s in samples) / len(samples)) ** 0.5) if samples else 0
db = 20 * math.log10(peak / 32768) if peak else -90
print(f"amostras: {len(samples)}  pico: {peak}  rms: {rms}  pico: {db:.1f} dBFS")
if peak < 300:
    print("SILENCIO: ha captura, mas nenhum sinal chega da mesa.")
    print("  -> suba o fader do canal / verifique MAIN L-R / cabecalho USB")
    sys.exit(2)
print("OK: sinal de audio presente.")
PY
else
  echo "python3 indisponivel; apenas o tamanho do buffer foi verificado."
fi
