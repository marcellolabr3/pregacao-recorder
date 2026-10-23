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
| history | PC -> celular | sim (ultimos eventos persistidos) |
| jobs | PC -> celular, progresso | sim |

Comandos: START, STOP, STATUS, DRIVE_STATUS, DRIVE_CONNECT, DRIVE_FINISH,
DRIVE_DISCONNECT, DRIVE_TEST, NLM_STATUS, NLM_REFRESH, NLM_RECONNECT, STORAGE_LIST,
STORAGE_SET, PREGACAO_LISTAR,
PREGACAO_OBTER, PREGACAO_CRIAR, PREGACAO_ATUALIZAR e PREGACAO_DELETAR.
START/STOP preservam idempotencia. Comandos com timestamp expirado sao recusados.
Trocar destino exige a protecao administrativa da API. O agente nao configura rede.
`NLM_REFRESH` agenda no PC uma verificacao e renovacao do NotebookLM e responde
sem esperar o Google; `NLM_STATUS` retorna apenas o estado, sem credenciais.
`NLM_RECONNECT` abre o login do NotebookLM no navegador do PC e responde
imediatamente para o APK mostrar que a entrada esta em andamento.
O estado retido tambem informa se ha token duravel e estudos em espera.
`PREGACAO_LISTAR` devolve ate 40 itens por resposta com `offset` e `total`,
ordenando proximas datas primeiro. Criar/editar/excluir usam a protecao
administrativa local do PC, sem enviar ou pedir PIN no celular. Atualizar e
excluir exigem `id` e `versao`; se outro celular alterou o registro, o ACK
indica `versao_desatualizada`. O evento `programacao_alterada` provoca recarga
da lista nos dois celulares. Cada celular usa ClientID MQTT proprio e filtra
ACKs pelo `req_id`.

## Configuracao

Consultar [EMQX.md](EMQX.md) e `.env.example`. Preservar device ID e credenciais
existentes na instalacao real para nao alterar os topics dos celulares
configurados. O laboratorio usa um `device_id` diferente para nao disputar
a sessao MQTT da instalacao pessoal.
O indicador de atividade local do agente usa heartbeat HTTP; nao e prova de
sessao MQTT conectada. Confirmacao funcional exige STATUS com ACK real.

O aplicativo atual e Flutter em `flutter/pregacao_controle/`.
APKs ja instalados nao sao atualizados por alterar arquivos no repositorio.
A primeira pagina Flutter permite consultar e manter a programacao. O APK
instalado so recebe essas mudancas depois de instalar a nova versao compilada.
