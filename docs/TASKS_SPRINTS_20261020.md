# Tasks e sprints - estabilidade e uso diario

Pedido de 20/10/2026: estabilizar o estado PC online/offline no APK,
fazer o progresso da tarefa concluida chegar a 100%, mostrar a programacao
na primeira pagina do painel e no APK, e iniciar o gravador com o Windows.

Regra de entrega: um commit ao concluir cada sprint. Testes e verificacoes
podem ocorrer durante as sprints; gerar APK, pacote e instalador finais somente
depois de todas as mudancas de codigo. Nao incluir contas, tokens, banco,
gravacoes ou perfil NotebookLM no Git.

## Sprint 1 - diagnostico de MQTT e plano

- [x] S1.1 Inventariar e encerrar os processos deste projeto neste PC; conferir
  que a porta 8080 ficou livre. O painel estava ocioso, sem gravacao ou tarefa.
- [x] S1.2 Examinar logs, ClientID, estados retidos e inicializacao automatica.
  O agente de desenvolvimento usa `pregacao-<device_id>` e o mesmo ID da edicao
  pessoal; o log mostra 761 desconexoes `rc=128` entre 19 e 20/10, com reconexoes
  a cada 1-2 segundos a partir de 09:11. A documentacao do EMQX descreve esse
  padrao quando dois clientes usam o mesmo ClientID com reconexao automatica.
  Isto e forte indicio de disputa de sessao, mas a causa remota exata ainda
  requer o evento `client_disconnected` do broker ou confirmacao do APK.
  Referencia: [eventos de conexao/desconexao do EMQX](https://docs.emqx.com/en/cloud/latest/best_practices/connection_disconnection_event_topic.html).
- [x] S1.3 O usuario confirmou que o APK estabilizou apos encerrar o agente
  deste PC. O SSD esta em outro PC; este repositorio e o laboratorio e precisa
  de identidade MQTT propria para nao derrubar a sessao da instalacao real.

## Sprint 2 - progresso da tarefa

- [x] S2.1 Fazer `CONCLUIDO` representar 100% da tarefa mesmo quando Drive ou
  WhatsApp opcionais foram pulados. Manter passos nao executados identificados
  como pulados; nao dizer que houve envio.
- [x] S2.2 Alinhar painel, evento MQTT retido e APK com o mesmo estado final;
  cobrir conclusao com e sem envio, espera, erro e reinicio.
- [x] S2.3 Suite Python relevante aprovada (159 testes), protocolo Flutter
  aprovado (34 testes), `flutter analyze` sem problemas, `node --check` e
  `git diff --check` aprovados. Commit da sprint realizado.

## Sprint 3 - programacao visivel no PC e no APK

- [x] S3.1 Levar a lista e os botoes de programacao para a primeira pagina
  do painel, mantendo autorizacao administrativa para alterar ou excluir.
- [x] S3.2 Expor listagem e operacoes de programacao por MQTT com respostas
  correlacionadas e limites de tamanho/validacao; manter o backend como fonte
  unica dos dados e nao publicar dados privados retidos sem necessidade.
- [x] S3.3 Criar a tela de programacao no APK, com consulta, criacao, edicao e
  exclusao, estados de carregamento/erro e atualizacao apos reconexao.
- [x] S3.4 Testar API, agente, protocolo e interface; commitar a sprint.
  Os testes direcionados de Python (141) e protocolo Flutter (35), a analise
  Flutter e o parser JavaScript passaram. A referencia visual da primeira
  pagina sera atualizada na integracao depois de fechar todas as mudancas.

## Sprint 4 - iniciar com o Windows

- [x] S4.1 Registrar inicializacao por usuario ao entrar no Windows para a
  edicao pessoal instalada, sem abrir navegador e sem iniciar copia duplicada.
  O atalho e registrado pelo instalador/atualizador; a execucao real do
  laboratorio iniciou painel e agente e uma segunda chamada manteve os PIDs.
- [x] S4.2 Permitir ativar/desativar no PC ja instalado; orientar o caso em
  que o SSD estiver ausente na entrada ou mudar de letra. A copia de
  laboratorio usa um ID MQTT distinto da instalacao real. O volume e
  identificado pelo numero de serie, com espera de 60 segundos na entrada.
- [x] S4.3 Validar sem reiniciar com gravacao/tarefas em curso; commitar a sprint.
  O laboratorio estava ocioso. O atalho foi registrado e resolveu D:; a
  abertura real iniciou painel e agente com ID proprio e a segunda chamada
  nao duplicou nenhum processo. O painel respondeu em 8080 e a lista da
  programacao respondeu. A suite Python completa passou. O reboot e o SSD
  real ficam para o aceite no PC de destino.

## Sprint 5 - integracao e entrega

- [x] S5.1 Suite Python e Flutter completas, 40 testes Flutter, analise Flutter,
  sintaxe JavaScript e referencias visuais da tela principal aprovadas.
- [x] S5.2 APK 2.7.0+13, pacote publico, instalador generico e atualizador
  pessoal gerados. Instalador, ZIP e APK copiados para o SSD e conferidos por
  SHA-256. A pasta pessoal do SSD foi atualizada, com 7.861 arquivos publicos
  validos e dados privados preservados. Nenhum instalador privado novo foi
  gerado a partir do laboratorio.
- [ ] S5.3 O agente pessoal abriu no SSD e respondeu online/status/listagem
  pelo MQTT sem desconexao observada; ao encerrar, o broker mostrou offline.
  Ainda faltam a prova nos dois celulares, um estudo real concluido a 100% e
  uma nova entrada no Windows do PC de destino.
- [x] S5.4 README, contexto, guias e evidencias atualizados; correcao do
  atualizador e documentacao enviadas no commit final da sprint.

O SSD foi conectado a este PC e esta pronto para ir ao PC de destino. A prova
de driver de audio, celulares e nova entrada no Windows depende desse PC.

Estado de trabalho: o usuario confirmou que nao quer pedir PIN no APK, operara
com dois celulares e autorizou a identidade MQTT separada do laboratorio. O
agente usa no PC as credenciais administrativas ja configuradas, sem pedir PIN
ao celular; o token MQTT salvo no telefone continua necessario para conectar.
O inicio automatico do laboratorio permanece registrado neste usuario Windows.
O inicio automatico pessoal foi testado e desativado apenas neste PC para nao
disputar a porta 8080; no PC de destino, use o comando incluido no SSD.
"Sem senha" significa sem PIN no APK; a senha e o token MQTT permanecem.
