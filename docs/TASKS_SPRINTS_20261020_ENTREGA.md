# Tasks e sprints: envio, desligamento e mapa mental

Data: 20/10/2026. Escopo: codigo do PC e painel web. Nenhum APK, instalador ou pacote sera gerado ate pedido expresso do usuario.

## Diagnostico inicial

- O painel tratava a linha `8. Enviando` como prova de entrega. Essa linha precede `sendMessage` e so prova tentativa. O emissor tambem nao aguardava confirmacao do destinatario.
- A sessao do WhatsApp fica em `PREGACAO_PIPELINE_HOME/whatsapp/auth`, especifica da instalacao. No laboratorio ela existe; o outro computador sem SSD nao esta acessivel aqui. A causa exata da falha naquele PC depende do seu log de handoff e da sessao local.
- O NotebookLM do projeto suporta gerar mapa mental interativo com `--instructions`, baixar JSON e selecionar o artefato por ID. A renderizacao visual sera feita no painel.

## Sprint 1 — diagnostico e contrato

- [x] Localizar fluxo de envio, autenticacao, estados e persistencia.
- [x] Definir estados separados para sessao, aceitacao pelo servidor WhatsApp e entrega confirmada.
- [x] Definir sprints e testes sem contato real nem desligamento real.

## Sprint 2 — WhatsApp confiavel

- [x] CONFIG: numeros multiplos com indicacao visivel dos destinos ativos.
- [x] CONFIG: conectar sessao via QR, verificar estado e orientar quando ausente.
- [x] Enviar para cada numero, guardar resultado por destinatario e marcar apenas o que puder ser comprovado.
- [x] Reenvio manual do PDF existente, sem repetir NotebookLM nem Drive.
- [x] Testes isolados de autenticacao, envio, reenvio e estados (sem envio real).

## Sprint 3 — desligamento apos conclusao

- [ ] CONFIG: habilitar e definir atraso em minutos, desabilitado por padrao.
- [ ] Agendar somente apos encerramento de gravacao, finalizacao, uploads e estudos; cancelar ao comecar nova atividade.
- [ ] Expor contagem/status e cancelamento manual; testar com comandos Windows simulados.

## Sprint 4 — mapa mental opcional

- [ ] CONFIG: checkbox e campo de instrucoes editavel.
- [ ] Gerar mapa no mesmo notebook, salvar JSON por estudo e expor visualizacao/arquivo no painel.
- [ ] Integrar erros, progresso, documentacao e testes isolados.

## Aceite final

- Testes automatizados e checagem no laboratorio, sem envio real ou desligamento real.
- Atualizar README e contexto; commit e push ao fim de cada sprint.
- Validacao com WhatsApp e NotebookLM reais no PC de destino continua dependente de acesso a esse PC.
