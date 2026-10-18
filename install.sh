#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# pregacao-recorder | instalacao completa em um Raspberry Pi 3 Model B+
#
#   1. copie a pasta do projeto para o Raspberry (scp, pen drive, git...)
#   2. rode:   sudo ./install.sh
#
# O script instala dependencias, cria diretorios, configura permissoes,
# registra o servico systemd e inicia o sistema. Pode ser rodado de novo
# para atualizar sem apagar gravacoes, configuracoes ou token do Google.
# ---------------------------------------------------------------------------
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="/opt/pregacao-recorder"
SERVICE="pregacao-recorder.service"
SERVICE_USER="${SUDO_USER:-pi}"
PY=python3
if [[ $EUID -ne 0 ]]; then
  echo "Execute com sudo:  sudo ./install.sh"
  exit 1
fi

echo "=== pregacao-recorder | instalacao ==="
echo "   origem : ${SRC_DIR}"
echo "   destino: ${APP_DIR}"

# usuario do servico: nunca root. Deriva de uma instalacao anterior (mais
# confiavel), depois do SUDO_USER de quem chamou o script, e por fim "pi".
# `sudo` chamado por um root ja existente devolve SUDO_USER=root - por isso
# a regra de exclusao abaixo.
SERVICE_USER="${SUDO_USER:-pi}"
if [[ -f "/etc/systemd/system/${SERVICE}" ]]; then
  PREV_USER="$(sed -n 's/^User=//p' "/etc/systemd/system/${SERVICE}" | head -1)"
  [[ -n "${PREV_USER}" && "${PREV_USER}" != "root" ]] && SERVICE_USER="${PREV_USER}"
fi
[[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]] && SERVICE_USER="pi"
echo "   usuario: ${SERVICE_USER}"

# 1. pacotes de sistema ------------------------------------------------------
echo "-> instalando pacotes do sistema"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip alsa-utils ffmpeg usbutils curl rsync \
  dnsmasq-base

# 2. estrutura de diretorios -------------------------------------------------
echo "-> copiando o projeto para ${APP_DIR}"
mkdir -p "${APP_DIR}"/{app,config,recordings,recovery,logs,scripts,systemd,data,web}
# preserva o que e do equipamento: configuracao salva, .env (PIN), token do
# Google e gravacoes. O codigo e sempre atualizado.
rsync -a \
  --exclude '.git' --exclude '__pycache__' --exclude '.venv' \
  --exclude '.pytest_cache' --exclude 'tests/' \
  --exclude 'recordings/' --exclude 'logs/' --exclude 'data/' \
  --exclude 'recovery/' --exclude 'config/config.json' \
  --exclude '.env' --exclude 'config/google_token.json' \
  --exclude 'android/' \
  --exclude 'flutter/' \
  --exclude 'site/' \
  --exclude 'CONTEXTO.md' \
  "${SRC_DIR}/" "${APP_DIR}/"

# credenciais do Google cadastradas pelo administrador: copia so na 1a vez
if [[ -f "${SRC_DIR}/config/google_credentials.json" && \
      ! -f "${APP_DIR}/config/google_credentials.json" ]]; then
  cp "${SRC_DIR}/config/google_credentials.json" "${APP_DIR}/config/"
  echo "-> credenciais do Google instaladas (config/google_credentials.json)"
fi

# 3. armazenamento externo (SSD/HD) ------------------------------------------
DISK_ROOT="/mnt/ssd"
if ! findmnt "${DISK_ROOT}" >/dev/null 2>&1; then
  echo "-> ${DISK_ROOT} nao montado: gravacoes ficarao em ${APP_DIR}/recordings"
  echo "   (veja INSTALACAO-RASPBERRY.md para montar o SSD automaticamente)"
else
  echo "-> armazenamento externo detectado em ${DISK_ROOT}"
  mkdir -p "${DISK_ROOT}/pregacoes"
fi

# 4. dependencias python -----------------------------------------------------
echo "-> instalando dependencias python"
if [[ ! -d "${APP_DIR}/.venv" ]]; then
  $PY -m venv --system-site-packages "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip -q
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q
VENV_PY="${APP_DIR}/.venv/bin/python"

# 5. arquivo de ambiente (PINs e segredos) -----------------------------------
if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "-> criando ${APP_DIR}/.env"
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  # gera PINs de 6 digitos com o modulo `secrets` (o pipe com tr/urandom
  # podia devolver 0-3 digitos, deixando o PIN vazio ou fraco)
  PIN="$(python3 -c 'import secrets; print(secrets.randbelow(900000) + 100000)')"
  ADMIN_PIN="$(python3 -c 'import secrets; print(secrets.randbelow(900000) + 100000)')"
  while [[ "${ADMIN_PIN}" == "${PIN}" ]]; do
    ADMIN_PIN="$(python3 -c 'import secrets; print(secrets.randbelow(900000) + 100000)')"
  done
  SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(30)[:40])')"
  sed -i "s/^PREGACAO_PIN=$/PREGACAO_PIN=${PIN}/" "${APP_DIR}/.env"
  sed -i "s/^PREGACAO_ADMIN_PIN=$/PREGACAO_ADMIN_PIN=${ADMIN_PIN}/" "${APP_DIR}/.env"
  sed -i "s/^PREGACAO_SECRET=$/PREGACAO_SECRET=${SECRET}/" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
  echo "   PIN de acesso        : ${PIN}   (grave em local seguro!)"
  echo "   PIN do administrador  : ${ADMIN_PIN}   (CONFIGURACOES AVANCADAS)"
fi

# 6. permissoes --------------------------------------------------------------
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"
# o rsync pode herdar 777 de um sistema de arquivos Windows (tar no PC):
# devolve 755 nas pastas e tira a escrita de terceiros dos arquivos
find "${APP_DIR}" -type d -exec chmod 755 {} +
find "${APP_DIR}" -type f -exec chmod o-w {} +
chmod 600 "${APP_DIR}/.env" 2>/dev/null || true
chmod +x "${APP_DIR}/install.sh" "${APP_DIR}/update.sh" \
          "${APP_DIR}/uninstall.sh" 2>/dev/null || true
chmod +x "${APP_DIR}/scripts/"* 2>/dev/null || true

# 7. servico systemd ---------------------------------------------------------
echo "-> instalando servico systemd"
cp "${APP_DIR}/systemd/${SERVICE}" /etc/systemd/system/
# aponta o ExecStart para o python do venv
sed -i "s|^ExecStart=.*|ExecStart=${VENV_PY} -m app.main|" "/etc/systemd/system/${SERVICE}"
sed -i "s|^User=.*|User=${SERVICE_USER}|" "/etc/systemd/system/${SERVICE}"
sed -i "s|^Group=.*|Group=${SERVICE_USER}|" "/etc/systemd/system/${SERVICE}"
systemctl daemon-reload
systemctl enable "${SERVICE}" >/dev/null 2>&1
systemctl restart "${SERVICE}"

# 7b. camada de rede (Ethernet, Wi-Fi, Access Point, Tailscale) ---------------
echo "-> configurando a camada de rede"

# NetworkManager e obrigatorio para listar/conectar Wi-Fi e emitir o Access
# Point de configuracao. Se o sistema usar outro gerenciador, o servico de
# gravacao continua funcionando normalmente (sao modulos independentes).
if command -v nmcli >/dev/null 2>&1; then
  systemctl enable NetworkManager >/dev/null 2>&1 || true
  systemctl start NetworkManager >/dev/null 2>&1 || true
else
  echo "   AVISO: NetworkManager ausente (Wi-Fi e Access Point indisponiveis)."
fi

# polkit: permite que o servico (sem sessao ativa) mande no NetworkManager
if [[ -f "${APP_DIR}/system/50-pregacao-network.rules" ]]; then
  sed "s/@USUARIO@/${SERVICE_USER}/g" \
    "${APP_DIR}/system/50-pregacao-network.rules" \
    > /etc/polkit-1/rules.d/50-pregacao-network.rules
  chmod 644 /etc/polkit-1/rules.d/50-pregacao-network.rules
  echo "   polkit     : /etc/polkit-1/rules.d/50-pregacao-network.rules"
fi

# sudoers fechado: so o Tailscale (status/autenticacao) roda como root
if [[ -f "${APP_DIR}/system/sudoers-pregacao-network" ]]; then
  sed "s/@USUARIO@/${SERVICE_USER}/g" \
    "${APP_DIR}/system/sudoers-pregacao-network" \
    > /etc/sudoers.d/pregacao-network
  chmod 440 /etc/sudoers.d/pregacao-network
  if visudo -cf /etc/sudoers.d/pregacao-network >/dev/null 2>&1; then
    echo "   sudoers    : /etc/sudoers.d/pregacao-network"
  else
    echo "   ERRO: sudoers invalido - removendo"
    rm -f /etc/sudoers.d/pregacao-network
    exit 1
  fi
fi

# avahi: hostname pregacao-pi.local na rede local (descoberta do painel)
mkdir -p /etc/avahi/services
if [[ -f "${APP_DIR}/system/avahi-pregacao-http.service" ]]; then
  cp "${APP_DIR}/system/avahi-pregacao-http.service" /etc/avahi/services/
  systemctl enable avahi-daemon >/dev/null 2>&1 || true
  systemctl restart avahi-daemon 2>/dev/null || true
  echo "   avahi      : pregacao-pi.local:8080"
fi

# Tailscale: acesso remoto PRIVADO (sem abrir porta no roteador, sem UPnP)
if ! command -v tailscale >/dev/null 2>&1; then
  echo "-> instalando Tailscale (repositorio oficial)"
  if curl -fsSL --max-time 90 https://tailscale.com/install.sh | sh; then
    echo "   Tailscale instalado"
  else
    echo "   AVISO: Tailscale nao instalado (sem Internet agora?)."
    echo "          O acesso local continua funcionando. Depois rode:"
    echo "          curl -fsSL https://tailscale.com/install.sh | sh"
  fi
fi
if command -v tailscale >/dev/null 2>&1; then
  systemctl enable tailscaled >/dev/null 2>&1 || true
  systemctl start tailscaled >/dev/null 2>&1 || true
fi

# watchdog de rede: mantem Ethernet/Wi-Fi/AP equilibrados e registra os
# eventos [NETWORK]/[TAILSCALE] no journal
NETWATCH="pregacao-netwatch.service"
if [[ -f "${APP_DIR}/systemd/${NETWATCH}" ]]; then
  cp "${APP_DIR}/systemd/${NETWATCH}" /etc/systemd/system/
  sed -i "s|^ExecStart=.*|ExecStart=${VENV_PY} -m app.network.watchdog|" \
    "/etc/systemd/system/${NETWATCH}"
  sed -i "s|^User=.*|User=${SERVICE_USER}|"   "/etc/systemd/system/${NETWATCH}"
  sed -i "s|^Group=.*|Group=${SERVICE_USER}|" "/etc/systemd/system/${NETWATCH}"
  systemctl daemon-reload
  systemctl enable "${NETWATCH}" >/dev/null 2>&1
  systemctl restart "${NETWATCH}"
  echo "   watchdog   : systemctl status ${NETWATCH}"
fi

# agente de controle remoto: mantem o equipamento alcancavel pelo APK de
# qualquer lugar. A unit e instalada SEMPRE; ela so passa a operar quando
# PREGACAO_REMOTE_HOST estiver no .env (sem configuracao o processo termina
# com sucesso e fica inativo, sem reiniciar em loop).
REMOTE="pregacao-remote.service"
if [[ -f "${APP_DIR}/systemd/${REMOTE}" ]]; then
  cp "${APP_DIR}/systemd/${REMOTE}" /etc/systemd/system/
  sed -i "s|^ExecStart=.*|ExecStart=${VENV_PY} -m app.remote.agent|" \
    "/etc/systemd/system/${REMOTE}"
  sed -i "s|^User=.*|User=${SERVICE_USER}|"   "/etc/systemd/system/${REMOTE}"
  sed -i "s|^Group=.*|Group=${SERVICE_USER}|" "/etc/systemd/system/${REMOTE}"
  systemctl daemon-reload
  systemctl enable "${REMOTE}" >/dev/null 2>&1
  systemctl restart "${REMOTE}" 2>/dev/null || true
  echo "   remoto     : systemctl status ${REMOTE}"
fi

# 8. comando `pregacao` ------------------------------------------------------
cat > /usr/local/bin/pregacao <<EOF
#!/usr/bin/env bash
export PREGACAO_HOME="${APP_DIR}"
cd "${APP_DIR}"
exec "${VENV_PY}" -m app.cli "\$@"
EOF
chmod +x /usr/local/bin/pregacao

echo
echo "=== instalacao concluida ==="
echo "  servico    : systemctl status ${SERVICE}"
echo "  rede       : systemctl status pregacao-netwatch.service"
echo "  comando    : pregacao status"
echo "  diagnostico: pregacao doctor"
echo "  interface  : http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080"
echo "                http://$(hostname).local:8080"
echo "  emergencia : sem rede, o equipamento emite PREGACAO-PI-XXXX"
echo "               (senha pregacao12345) em http://192.168.50.1:8080"
echo "  remoto     : Tailscale pelo painel (CONFIGURACOES AVANCADAS > REDE)"
echo "  logs rede  : journalctl -u pregacao-netwatch -f"
echo "  PINs       : veja ${APP_DIR}/.env"
echo
echo "Proximos passos:"
echo "  1. pregacao check          # confirma que ha sinal de audio"
echo "  2. abra a interface pelo celular e siga o ASSISTENTE DE PRIMEIRO ACESSO"
echo "  3. conecte o Google Drive pela propria interface (CONECTAR CONTA GOOGLE)"
echo "  4. credenciais do Google (uma unica vez, so o administrador):"
echo "     docs/GOOGLE_DRIVE.md"
