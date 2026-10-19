# Controle remoto MQTT

O agente `app/remote/agent.py` roda separado do servidor no Windows e chama sua
API em loopback. `iniciar-tudo.bat` inicia gravador e agente. Para iniciar somente
o agente, com o gravador ja rodando, usar `iniciar-tudo.bat --somente-agente`.
Se o agente cair, a captura local e suas filas continuam.

## Topics

Sob `pregacao/<device_id>/`:

| Topic | Direcao | Retido |
|---|---|---|
| cmd | celular -> PC | nao |
| ack | PC -> celular | nao |
| state | PC -> celular | sim |
| avail | PC -> celular, com LWT | sim |
| events | PC -> celular | nao |
| jobs | PC -> celular, progresso | sim |

Comandos: START, STOP, STATUS, DRIVE_STATUS, DRIVE_CONNECT, DRIVE_FINISH,
DRIVE_DISCONNECT, DRIVE_TEST, STORAGE_LIST e STORAGE_SET.
START/STOP preservam idempotencia. Comandos com timestamp expirado sao recusados.
Trocar destino exige a protecao administrativa da API. O agente nao configura rede.

## Configuracao

Consultar [EMQX.md](EMQX.md) e `.env.example`. Preservar device ID e credenciais
existentes para nao alterar os topics dos celulares configurados.
O indicador de atividade local do agente usa heartbeat HTTP; nao e prova de
sessao MQTT conectada. Confirmacao funcional exige STATUS com ACK real.

O aplicativo atual e Flutter em `flutter/pregacao_controle/`. A fonte Kotlin em
`android/` e legada; seu menu de configuracao de rede foi retirado da fonte.
APKs ja instalados nao sao atualizados por alterar arquivos no repositorio.
A tela Flutter de cadastro de pregacoes ainda nao esta implementada.
