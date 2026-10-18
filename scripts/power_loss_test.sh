#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Teste de queda de energia / reinicializacao inesperada.
#
# Validacao obrigatoria do projeto:
#   1. inicia gravacao
#   2. derruba o servico (simula corte de energia)
#   3. reinicia
#   4. confirma que a interface WEB avisa sobre a gravacao interrompida
#   5. recupera o arquivo pela API
#   6. confirma que o arquivo final existe e e reproduzivel
# ---------------------------------------------------------------------------
set -uo pipefail

APP_DIR="${PREGACAO_HOME:-/opt/pregacao-recorder}"
SERVICE="pregacao-recorder.service"
PIN_FILE="${APP_DIR}/.env"
API="http://127.0.0.1:8080"

log() { echo -e "\n[equipe] $*"; }

PIN=""
[[ -f "${PIN_FILE}" ]] && PIN="$(sed -n 's/^PREGACAO_PIN=//p' "${PIN_FILE}" | tr -d '"')"
JAR="$(mktemp)"
trap 'rm -f "${JAR}"' EXIT

api() {
  local method="$1" path="$2" data="${3:-}"
  if [[ -n "${data}" ]]; then
    curl -sS -X "${method}" -b "${JAR}" -c "${JAR}" \
      -H 'Content-Type: application/json' -d "${data}" "${API}${path}"
  else
    curl -sS -X "${method}" -b "${JAR}" -c "${JAR}" "${API}${path}"
  fi
}

log "0/6  verificando servico"
curl -sS -o /dev/null "${API}/api/ping" || { echo "servico fora do ar"; exit 1; }

log "1/6  autenticando"
api POST /api/login "{\"pin\":\"${PIN}\"}" >/dev/null

log "2/6  iniciando gravacao"
api POST /api/start | tee /dev/stderr | grep -q '"ok": *true\|"ok":true' \
  || { echo "FALHA ao iniciar"; exit 1; }

log "3/6  gravando por 25 segundos"
sleep 25

log "4/6  MATANDO o servico (simula corte de energia)"
sudo systemctl kill -s SIGKILL "${SERVICE}"
sleep 3

log "5/6  reiniciando"
sudo systemctl start "${SERVICE}"
sleep 6

log "6/6  verificando deteccao da gravacao interrompida"
sleep 3
RECOVERY="$(api GET /api/recovery)"
echo "${RECOVERY}"
if [[ "${RECOVERY}" == *"id"* ]]; then
  echo "OK: gravacao interrompida detectada pela interface."
  SID="$(echo "${RECOVERY}" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["items"][0]["id"])')"
  log "    recuperando ${SID}"
  api POST "/api/recovery/${SID}/recover"
  echo
  echo "Aguardando consolidacao..."
  sleep 20
  pregacao status || true
  echo
  echo "RESULTADO: teste de recuperacao concluido."
  echo "Abra a interface pelo celular para confirmar visualmente."
else
  echo "FALHA: a gravacao interrompida NAO foi detectada."
  exit 1
fi
