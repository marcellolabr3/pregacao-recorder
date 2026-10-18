#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# pregacao-recorder | desinstalacao
#
#   sudo ./uninstall.sh              # remove o programa, MANTENDO gravacoes
#   sudo ./uninstall.sh --tudo       # remove programa E gravacoes (confirma!)
#
# Nenhuma gravacao e apagada sem confirmacao explicita.
# ---------------------------------------------------------------------------
set -euo pipefail

APP_DIR="/opt/pregacao-recorder"
SERVICE="pregacao-recorder.service"
APAGAR_DADOS=0

[[ "${1:-}" == "--tudo" ]] && APAGAR_DADOS=1

if [[ $EUID -ne 0 ]]; then
  echo "Execute com sudo:  sudo ./uninstall.sh"
  exit 1
fi

echo "=== pregacao-recorder | desinstalacao ==="
echo
echo "Isso vai:"
echo "  [x] parar e desativar o servico ${SERVICE}"
echo "  [x] remover o comando 'pregacao'"
if [[ ${APAGAR_DADOS} -eq 1 ]]; then
  echo "  [!] APAGAR gravacoes, configuracoes e token do Google em ${APP_DIR}"
else
  echo "  [ ] manter gravacoes e configuracoes em ${APP_DIR} (padrao)"
fi
echo

if [[ ${APAGAR_DADOS} -eq 1 ]]; then
  echo "ATENCAO: gravacoes e configuracoes serao PERDIDES."
  echo "Digite exatamente  SIM  para confirmar:"
  read -r CONF
  if [[ "${CONF}" != "SIM" ]]; then
    echo "Cancelado. Nada foi alterado."
    exit 1
  fi
  # exige tambem o nome do servico, evitando confirmacao automatica
  echo "Digite o nome do servico (${SERVICE}) para confirmar de novo:"
  read -r CONF2
  if [[ "${CONF2}" != "${SERVICE}" ]]; then
    echo "Cancelado. Nada foi alterado."
    exit 1
  fi
fi

echo "-> parando o servico"
systemctl stop "${SERVICE}" 2>/dev/null || true
systemctl disable "${SERVICE}" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE}"

echo "-> removendo a camada de controle remoto"
systemctl stop pregacao-remote.service 2>/dev/null || true
systemctl disable pregacao-remote.service 2>/dev/null || true
rm -f /etc/systemd/system/pregacao-remote.service

echo "-> removendo a camada de rede"
systemctl stop pregacao-netwatch.service 2>/dev/null || true
systemctl disable pregacao-netwatch.service 2>/dev/null || true
rm -f /etc/systemd/system/pregacao-netwatch.service
rm -f /etc/polkit-1/rules.d/50-pregacao-network.rules
rm -f /etc/sudoers.d/pregacao-network
rm -f /etc/avahi/services/pregacao-http.service
# o Tailscale NAO e desinstalado: ele pode ser usado por outro equipamento.
# Para remover:  sudo apt-get remove tailscale

rm -f /usr/local/bin/pregacao
systemctl daemon-reload

if [[ ${APAGAR_DADOS} -eq 1 ]]; then
  echo "-> apagando ${APP_DIR} (inclui gravacoes)"
  rm -rf "${APP_DIR}"
  echo "-> removendo servico e comando"
else
  echo "-> programa removido"
  echo "   Dados preservados em ${APP_DIR}"
  echo "   Para remove-los depois:  sudo ./uninstall.sh --tudo"
fi

echo
echo "=== desinstalacao concluida ==="
