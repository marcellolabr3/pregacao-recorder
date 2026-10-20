# Aceite da instalacao pessoal - sprint 3

Use o instalador e o guia atualizados. Registre somente versao, resultado e
erro observado; nunca senhas, tokens, cookies, QRs ou dados pessoais.

## Estado

Sprint 3 iniciada com validacao isolada neste PC. Os testes abaixo continuam
pendentes no Windows limpo e no computador destino. Teste automatizado com
dispositivos/contas simulados nao comprova captura nem acesso a contas reais.

## Instalar e configurar

- [ ] Registrar PC/Windows e nome do instalador; conferir o `.exe.sha256`.
- [ ] Instalar em Windows x64 sem Python/Node/FFmpeg/Git de desenvolvimento.
- [ ] Abrir pelo atalho, conferir porta e executar `Verificar Pacote.cmd`.
- [ ] Selecionar dispositivo, testar sinal, salvar e conferir apos reabrir.
- [ ] Selecionar pasta/disco com espaco livre; salvar e conferir apos reabrir.
- [ ] Configurar MQTT no cartao administrativo; manter ID distinto se dois PCs
  puderem ligar. Conferir credencial/ACL dos topics no broker.
- [ ] Reiniciar Windows com tarefas concluidas, abrir atalho e conferir CONFIG.

## Funcionalidades atuais

- [ ] Gravar audio curto real, parar, ouvir MP3 e conferir duracao/historico/pasta.
- [ ] Repetir gravacao sem internet; reconectar depois e conferir filas atuais.
- [ ] Trocar destino por uma pasta de teste; conferir nova gravacao e preservacao
  dos arquivos anteriores. Destino ausente deve recusar gravar sem fallback.
- [ ] Conferir recuperacao atual de gravacao interrompida usando somente audio de teste.
- [ ] Cadastrar pregacao e importar CSV/XLSX de teste, sem sobrescrever dados reais.
- [ ] Conectar Drive e testar envio de um audio de teste; conferir arquivo remoto.
- [ ] Renovar/diagnosticar NotebookLM; gerar estudo e abrir o PDF.
- [ ] Parear WhatsApp; conferir destinatario e receber o PDF de teste.
- [ ] Parear APK atual e enviar STATUS; conferir ACK e estado atual.
- [ ] Pelo celular, iniciar/parar uma gravacao de teste e conferir progresso/MP3.
- [ ] Reabrir o programa; conferir preferencias, PINs, identidade e ausencia de duplicatas.
- [ ] Reinstalar ocioso; conferir backup, banco, configuracoes e audios preservados.

## Registro

| Ambiente / versao | Item | Resultado / evidencia |
|---|---|---|
| Windows limpo | Instalacao e runtimes | Pendente |
| PC destino | Audio real e offline | Pendente |
| PC destino | Pasta, historico, recuperacao e cadastro/importacao | Pendente |
| PC destino | Drive e NotebookLM/PDF | Pendente |
| PC destino | WhatsApp e destinatario conferido | Pendente |
| PC destino + celular | MQTT/STATUS/ACK e comandos | Pendente |

O aceite exige os resultados reais acima. Registre impedimentos com passos de
reproducao antes de considerar a entrega pronta.
