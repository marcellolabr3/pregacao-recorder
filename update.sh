#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# pregacao-recorder | atualizacao segura
#
#   sudo ./update.sh                 # atualiza /opt a partir desta pasta
#   sudo ./update.sh /outro/caminho  # atualiza a partir de outra pasta
#
# NUNCA apaga: gravacoes, configuracoes (.env + config.json), token do
# Google nem historico. Um backup e gerado antes de qualquer alteracao.
# ---------------------------------------------------------------------------
set -euo pipefail

ORIGEM="${1:-$(cd "$(dirname "$0")" && pwd)}"
APP_DIR="/opt/pregacao-recorder"
SERVICE="pregacao-recorder.service"

if [[ $EUID -ne 0 ]]; then
  echo "Execute com sudo:  sudo ./update.sh"
  exit 1
fi

if [[ ! -f "${ORIGEM}/requirements.txt" ]]; then
  echo "ERRO: '${ORIGEM}' nao parece ser o projeto pregacao-recorder."
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/var/backups/pregacao-recorder"
BACKUP_FILE="${BACKUP_DIR}/backup-${TS}.tar.gz"

echo "=== pregacao-recorder | atualizacao ==="
echo "   origem: ${ORIGEM}"

# usuario do servico: sempre o MESMO da instalacao anterior (nunca root).
# `sudo` chamado por um root ja existente devolve SUDO_USER=root, entao a
# fonte de verdade e o User= do proprio unit.
SERVICE_USER="$(sed -n 's/^User=//p' "/etc/systemd/system/${SERVICE}" 2>/dev/null | head -1)"
[[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]] && SERVICE_USER="${SUDO_USER:-pi}"
[[ -z "${SERVICE_USER}" || "${SERVICE_USER}" == "root" ]] && SERVICE_USER="pi"
echo "   usuario: ${SERVICE_USER}"

# 1. backup antes de qualquer coisa ------------------------------------------
echo "-> gerando backup de configuracoes em ${BACKUP_FILE}"
mkdir -p "${BACKUP_DIR}"
tar -czf "${BACKUP_FILE}" \
  -C "${APP_DIR}" \
  $( [[ -f "${APP_DIR}/.env" ]] && echo ".env" ) \
  $( [[ -d "${APP_DIR}/config" ]] && echo "config" ) \
  $( [[ -d "${APP_DIR}/data" ]] && echo "data" ) \
  $( [[ -d "${APP_DIR}/logs" ]] && echo "logs" ) 2>/dev/null || true
echo "   backup: ${BACKUP_FILE}  (restaure com: tar -xzf ...)"

# 2. para os servicos --------------------------------------------------------
echo "-> parando os servicos"
systemctl stop "${SERVICE}" 2>/dev/null || true
systemctl stop pregacao-netwatch.service 2>/dev/null || true

# 3. atualiza apenas o CODIGO ------------------------------------------------
echo "-> copiando arquivos atualizados (preserva dados do equipamento)"
rsync -a \
  --exclude '.git' --exclude '__pycache__' --exclude '.venv' \
  --exclude '.pytest_cache' --exclude 'tests/' \
  --exclude 'recordings/' --exclude 'logs/' --exclude 'data/' \
  --exclude 'recovery/' --exclude 'config/' --exclude '.env' \
  --exclude 'android/' \
  --exclude 'flutter/' \
  --exclude 'site/' \
  --exclude 'CONTEXTO.md' \
  "${ORIGEM}/" "${APP_DIR}/"

# credenciais do Google so entram se nao existirem ainda no equipamento
if [[ -f "${ORIGEM}/config/google_credentials.json" && \
      ! -f "${APP_DIR}/config/google_credentials.json" ]]; then
  cp "${ORIGEM}/config/google_credentials.json" "${APP_DIR}/config/"
fi

# 4. dependencias ------------------------------------------------------------
echo "-> atualizando dependencias python"
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

# 4b. arquivos de sistema da camada de rede (idempotente) ---------------------
echo "-> atualizando arquivos de rede (polkit, sudoers, avahi, watchdog)"
# servico principal: o arquivo do repositorio e um template, e User/Group/
# ExecStart sao preenchidos aqui (mesma logica do install.sh). Assim mudancas
# de endurecimento do unit chegam ao equipamento na atualizacao.
if [[ -f "${APP_DIR}/systemd/${SERVICE}" ]]; then
  cp "${APP_DIR}/systemd/${SERVICE}" "/etc/systemd/system/${SERVICE}"
  sed -i "s|^ExecStart=.*|ExecStart=${APP_DIR}/.venv/bin/python -m app.main|" \
    "/etc/systemd/system/${SERVICE}"
  sed -i "s|^User=.*|User=${SERVICE_USER}|"   "/etc/systemd/system/${SERVICE}"
  sed -i "s|^Group=.*|Group=${SERVICE_USER}|" "/etc/systemd/system/${SERVICE}"
fi
if [[ -f "${APP_DIR}/system/50-pregacao-network.rules" ]]; then
  sed "s/@USUARIO@/${SERVICE_USER}/g" \
    "${APP_DIR}/system/50-pregacao-network.rules" \
    > /etc/polkit-1/rules.d/50-pregacao-network.rules
  chmod 644 /etc/polkit-1/rules.d/50-pregacao-network.rules
fi
if [[ -f "${APP_DIR}/system/sudoers-pregacao-network" ]]; then
  sed "s/@USUARIO@/${SERVICE_USER}/g" \
    "${APP_DIR}/system/sudoers-pregacao-network" \
    > /etc/sudoers.d/pregacao-network
  chmod 440 /etc/sudoers.d/pregacao-network
  visudo -cf /etc/sudoers.d/pregacao-network >/dev/null \
    || { echo "ERRO: sudoers invalido"; rm -f /etc/sudoers.d/pregacao-network; exit 1; }
fi
mkdir -p /etc/avahi/services
if [[ -f "${APP_DIR}/system/avahi-pregacao-http.service" ]]; then
  cp "${APP_DIR}/system/avahi-pregacao-http.service" /etc/avahi/services/
fi
if [[ -f "${APP_DIR}/systemd/pregacao-netwatch.service" ]]; then
  cp "${APP_DIR}/systemd/pregacao-netwatch.service" /etc/systemd/system/
  sed -i "s|^ExecStart=.*|ExecStart=${APP_DIR}/.venv/bin/python -m app.network.watchdog|" \
    /etc/systemd/system/pregacao-netwatch.service
  sed -i "s|^User=.*|User=${SERVICE_USER}|"   /etc/systemd/system/pregacao-netwatch.service
  sed -i "s|^Group=.*|Group=${SERVICE_USER}|" /etc/systemd/system/pregacao-netwatch.service
fi
if [[ -f "${APP_DIR}/systemd/pregacao-remote.service" ]]; then
  cp "${APP_DIR}/systemd/pregacao-remote.service" /etc/systemd/system/
  sed -i "s|^ExecStart=.*|ExecStart=${APP_DIR}/.venv/bin/python -m app.remote.agent|" \
    /etc/systemd/system/pregacao-remote.service
  sed -i "s|^User=.*|User=${SERVICE_USER}|"   /etc/systemd/system/pregacao-remote.service
  sed -i "s|^Group=.*|Group=${SERVICE_USER}|" /etc/systemd/system/pregacao-remote.service
fi

# 5. volta a rodar -----------------------------------------------------------
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}" 2>/dev/null || true
systemctl daemon-reload
# `systemctl enable` e obrigatorio: apenas reiniciar deixa o unit DESLIGADO
# para o proximo boot, e sem o watchdog a rede fica sem recuperacao automatica.
# O enable e idempotente, entao pode rodar a cada atualizacao.
systemctl enable "${SERVICE}" >/dev/null 2>&1 || true
systemctl enable pregacao-netwatch.service >/dev/null 2>&1 || true
systemctl enable pregacao-remote.service >/dev/null 2>&1 || true
systemctl restart pregacao-netwatch.service 2>/dev/null || true
# o agente de controle remoto termina rapido e fica inativo quando nao ha
# PREGACAO_REMOTE_HOST - por isso o restart e "|| true"
systemctl restart pregacao-remote.service 2>/dev/null || true
systemctl restart avahi-daemon 2>/dev/null || true
systemctl restart "${SERVICE}"
sleep 3

if systemctl is-active --quiet "${SERVICE}"; then
  echo
  echo "=== atualizacao concluida - servico ativo ==="
else
  echo
  echo "ATENCAO: o servico nao subiu. Veja: journalctl -u ${SERVICE} -n 50"
  exit 1
fi

echo "  backup antigo: ${BACKUP_FILE}"
echo "  historico    : journalctl -u ${SERVICE} -n 50"
echo "  rede/watchdog: journalctl -u pregacao-netwatch -n 50"
