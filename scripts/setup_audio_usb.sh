#!/usr/bin/env bash
# Regra udev para tornar a interface de audio USB estavel entre reinicios.
# Uso: sudo ./scripts/setup_audio_usb.sh
set -euo pipefail

RULE_FILE="/etc/udev/rules.d/99-pregacao-audio.rules"

echo "=== interfaces de audio atuais ==="
arecord -l || true
echo

USB_SEQ="$(grep -i -E 'audio|sound' /sys/class/sound/card*/device/uevent 2>/dev/null | head -n1 || true)"

cat > "${RULE_FILE}" <<'EOF'
# pregacao-recorder - garante que a interface USB de audio seja sempre card0
# quando ela for a unica placa USB conectada.
# A aplicacao nao depende disso: o modo "auto" ja detecta a placa USB.
ACTION=="add", SUBSYSTEM=="sound", ATTRS{bInterfaceClass}=="01", \
  ENV{ID_USB_DRIVER}=="snd-usb-audio", SYMLINK+="pregacao/audio", \
  TAG+="systemd"
EOF

udevadm control --reload-rules
udevadm trigger --subsystem-match=sound
echo "regra instalada em ${RULE_FILE}"
echo
echo "Para fixar o nome do dispositivo, prefira a tela de CONFIGURACAO da interface web"
echo "ou o campo audio.device em config/config.json (ex.: hw:1,0)."
