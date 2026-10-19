# Configuracao MQTT/TLS

O broker liga o PC aos celulares. Usar TLS (porta configurada, normalmente 8883)
e credenciais distintas para o processo do PC e o usuario operador.
O projeto nao configura a rede nem o firewall do Windows.

## Variaveis

- `PREGACAO_REMOTE_HOST`, `PREGACAO_REMOTE_PORT`, `PREGACAO_REMOTE_TLS`.
- `PREGACAO_DEVICE_ID`: mesmo identificador configurado no celular.
- `PREGACAO_REMOTE_USERNAME/PASSWORD`: credencial do PC.
- `PREGACAO_OPERATOR_TOKEN`: credencial do usuario operador no broker/celular.
- `PREGACAO_REMOTE_ENABLED=auto`: ativo quando ha host; `0` desliga.
- `PREGACAO_REMOTE_INTERVAL`: intervalo de consulta do estado.

Preservar valores existentes; nao renovar credenciais durante atualizacao de codigo.

## Permissoes do broker

| Usuario | Publicar | Assinar |
|---|---|---|
| PC | `pregacao/<id>/{avail,state,events,ack,jobs}` | `pregacao/<id>/cmd` |
| operador | `pregacao/<id>/cmd` | `pregacao/<id>/{avail,state,events,ack,jobs}` |

As chaves sao uma abreviacao: criar as regras para cada topic conforme a sintaxe
do provedor. Negar outros dispositivos/topics. Nao enviar comandos retidos.

Depois de iniciar o agente, validar no celular STATUS/ACK e estado atual.
`scripts/emqx_check.py` e um teste ativo: inicia/para gravacao; nao executar
sem preparar o equipamento e autorizar esse ciclo.
