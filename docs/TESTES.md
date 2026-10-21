# Validacao - Windows

## Interface, cancelamento e APK 2.8 (21/10/2026)

- Suite Python completa com `pytest -q` passou; testes direcionados de
  cancelamento, API e agente MQTT passaram depois do ajuste de recuperacao.
  A suite nao fez captura real, upload ou envio.
- `node --check web/static/app.js` e smoke Playwright isolado passaram. O
  navegador confirmou navegacao pelas abas e que cada botao salva somente os
  campos da propria aba; audio, destino e MQTT avancados continuam operaveis.
- `flutter test --no-pub` passou com 40 testes, inclusive as tres referencias
  visuais atualizadas; `flutter analyze --no-pub` informou zero problemas.
  A referencia GRAVANDO foi inspecionada em tela estreita e o corte da barra
  superior foi corrigido.
- `flutter build apk --release --no-pub` produziu
  `dist-pacote/PregacaoControle-2.8.apk` (2.8.0+14, versionCode 14).
  `apksigner verify -v` passou e o certificado SHA-256 coincide com o APK
  2.6 anterior (`0035d8609e5f6456cb558cce23224d753737f31e010d7b2dae9ece985d3572e5`).
  SHA-256 do arquivo: `CC3D4E3DBC3E1F3A2AF4F592C98F975330A22E60DE574CAB9FB7FD20F3779CC2`.
- O usuario relatou que o teste funcional anterior foi bem-sucedido. Esta
  versao do descarte e do novo visual foi validada em testes isolados; falta
  confirmar em uma gravacao real e nos dois celulares. A unidade E: vista
  neste PC estava vazia, sem a pasta pessoal; por isso o instalador completo
  anterior ainda contem a versao anterior ate o SSD correto ser conectado.

## Ciclo de envio, desligamento e mapa mental (20/10/2026)

- A suite Python completa passou com `.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q`.
- `node --check` validou o painel e o emissor WhatsApp; testes isolados cobrem
  numeros multiplos, reenvio sem regenerar, mapa opcional/artefato especifico,
  API de visualizacao e bloqueio do desligamento pelas filas.
- O CLI NotebookLM da instalacao local informa versao 0.8.5 e suporta
  `generate mind-map --kind interactive --instructions`; o fluxo real de geracao
  nao foi executado. A sessao WhatsApp local conectou com `send.js --status`,
  sem enviar mensagem. Nenhum comando de desligamento real foi executado.
- O outro PC e o SSD nao estavam acessiveis: causa exata do envio anterior,
  recebimento real, mapa real e desligamento real continuam para aceite no destino.
- Nenhum APK, pacote, instalador ou atualizador foi gerado neste ciclo.
- Integracao em servicos reais do laboratorio: estado `IDLE`, zero filas
  pendentes; gravador e agente reiniciados e reconhecidos na segunda chamada do
  launcher. GET do painel/config/estudos/desligamento respondeu com campos novos;
  POST `/api/whatsapp/check` confirmou conexao sem envio; MQTT conectado.
  Depois do ajuste de `pythonw.exe`, a suite Python completa passou novamente.
- `flutter test --no-pub test/protocolo_test.dart`: 37 testes passaram apos a
  correcao dos rotulos de aceite/envio incerto; nenhuma compilacao de APK.

## Suite Python

Revisao da sprint 2 em 19/10/2026: **488 testes passaram em 42,17 s** em copia temporaria
com somente fontes, testes, defaults, empacotamento e vendor publico. Nenhuma
credencial, banco, gravacao ou ambiente instalado real foi copiado. A base anterior
tinha 350 testes na sprint 1; as regressoes novas cobrem perfil de login/pipeline,
identidade entre instalacoes, bootstrap, pareamento administrativo e instalador.
Os fluxos de configuracao tambem cobrem audio selecionado antes de salvar,
interface ausente, taxa/canais, lote invalido, falha de escrita, salvar/reabrir
destino/Drive/MQTT, permissoes, segredos vazios e porta MQTT numerica no painel.
`node --check web/static/app.js` e `git diff --check` passaram.

Para repetir com o venv preparado:

```powershell
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short
node --check web/static/app.js
```

`tests/conftest.py` define home temporario antes dos imports e usa bancos isolados.
Para a validacao final desta tarefa foi utilizada tambem uma copia das fontes fora
do projeto. Nao executar scripts de teste ativo contra o servidor real por engano.

## Sprint 3 iniciada - configuracao e instalacao

- Instalador atualizado: `dist-pacote/PregacaoRecorder-Instalar-sprint2-20261020T000353363243Z.exe`
  (515,9 MiB). SHA256 do `.exe.sha256` adjacente conferido; compilacao Inno passou.
- Pacote correspondente: `dist-pacote/PregacaoRecorder-sprint2-20261020T000353363243Z/`,
  7.858 arquivos inventariados, zero extras. Comparacao de 50 fontes/guia/vendor
  com a arvore atual passou; `source_revision=96add70-dirty`.
- Metadados: `.bundle-cache/sprint2-current-artifact.json`; nao e release com aceite no destino.
- As 11 provas do instalador foram repetidas com fixtures novas e passaram:
  instalacao com espacos/acentos/&, backup/reinstalacao, preservacao de SQLite,
  audios/perfis e recusas por processo ativo, lock, junction e falha de backup.
- Evidencia: `.bundle-cache/sprint3-installer-fixtures-20261019/smoke-report.json`.
- Suite completa: `.bundle-cache/sprint2-isolated-pytest.json` e log adjacente.
- Chromium privado offline passou no roteiro `tests/smoke_config_ui.py`: primeiro
  uso, selecao/teste antes de salvar, taxa/canais, pasta, reabertura, interface
  desconectada e MQTT com porta numerica, revelacao/limpeza e segredos preservados.
  Evidencia: `.bundle-cache/sprint3-config-ui-final.log` (exit 0).
- Smoke do pacote atualizado passou com PATH isolado: imports privados, PDF,
  XLSX, Chromium/headless persistente, NotebookLM, Node/WhatsApp sem conexao,
  FFmpeg/DirectShow, MP3 sintetico e diagnostico sem criar configuracao.
- O payload real foi compilado tambem em modo de teste sem registro/atalho e
  instalado numa pasta temporaria com espacos/acentos/&. Os 7.858 hashes
  instalados conferem. Diagnostico com PATH sem ferramentas de desenvolvimento,
  API administrativa, audio selecionado sem salvar, lote invalido, segredos
  preservados, identidade/caminhos e reabertura em processo novo passaram.
- Evidencia: `.bundle-cache/sprint3-full-install-20261020T001205Z/report.json`
  e `.bundle-cache/sprint3-full-install-latest.json` (PASS). Hardware/contas sao
  simulados nessa prova; ela nao inicia captura ou conexao real.
- Limite observado: o primeiro destino de teste tinha 129 caracteres e excedia
  MAX_PATH em recursos do Chromium. O arquivo existia via prefixo estendido,
  mas a leitura Python comum falhou em um caminho de 264 caracteres. A prova
  foi repetida com raiz curta (caminho maximo abaixo de 260) e passou. Preferir
  `%LOCALAPPDATA%\PregacaoRecorder`; nao tratar pastas profundas como validadas.
- Configuracao/aceite pessoal no PC destino e Windows limpo continuam pendentes;
  roteiro em [ACEITE_WINDOWS.md](ACEITE_WINDOWS.md), incluido no pacote.
- Nenhuma captura fisica, conta, broker, envio ou servidor de desenvolvimento foi
  alterado nesta etapa. Os testes de configuracao usam fronteiras simuladas.

Arquivos alterados nesta conclusao dos fluxos 2.2/2.3 e inicio da sprint 3:

- `app/api/routes.py`, `app/audio/device.py`, `app/config.py`, `app/launcher.py`.
- `app/remote/agent.py`, novo `app/remote/settings.py`.
- `web/static/app.js`, `web/templates/index.html`.
- `tests/test_audio.py`, `tests/test_bundled_runtime.py`, `tests/test_launcher.py`,
  `tests/test_remote_pairing_ui.py`, novos `tests/test_config_audio_flow.py`,
  `tests/test_remote_config.py` e `tests/smoke_config_ui.py`.
- `packaging/build_bundle.py`, `packaging/build_installer.py`, `packaging/README.md`.
- `docs/CODEX_CONTEXT.md`, `docs/SPRINTS.md`, `docs/TASK_DISTRIBUICAO_WINDOWS.md`,
  `docs/TESTES.md`, `docs/GUIA_INSTALACAO_WINDOWS.md`, novo `docs/ACEITE_WINDOWS.md`.

As alteracoes anteriores que ja estavam sem commit foram preservadas.

## Cobertura da retirada

- Rotas de configuracao de interfaces inexistentes (GET/POST retornam 404).
- Comandos antigos de gestao de rede recusados; gravacao/Drive/storage preservados.
- Discos/pastas: consultas sem criar diretorios, recusa de caminho relativo,
  arquivo, volume ausente e falta de permissao; pasta criada apenas ao escolher.
- Captura DirectShow mesmo se houver ferramenta legada no PATH.
- Home padrao na pasta do projeto; override e destino configurado preservados.
- Configuracoes antigas ignoradas sem reescrever o arquivo local.
- Formularios HTML independentes e campos associados ao formulario correto.
- Nova captura recusada quando destino esta indisponivel.

## Navegador (evidencias da sessao anterior)

Chromium/Playwright headless, APIs simuladas e nenhuma acao no servidor real:
boot, CONFIG, area avancada, abrir/fechar cadastro e salvar avancadas passaram.
Zero erros JavaScript e zero chamadas de administracao de rede.
A sintaxe JavaScript passou em `node --check`. Navegador real tambem abriu sem
erros JS, com formulario presente e sem controles de rede do equipamento.
O servidor real foi reiniciado apos conferir ausencia de captura, uploads, estudos
e login em execucao. APIs de integracoes/pregacoes/modelo retornaram 200; painel
serve o cache `nlm2`. Os dois estudos em espera foram preservados.

## Renovacao de login NotebookLM

- Sessao nova do navegador dedicado, prazo de 10 minutos, monitoramento assincrono
  e uma unica janela; nenhuma alteracao no pacote instalado ou pipeline externo.
- Codigo zero no login sem auth check passivo valido nao libera os estudos.
- Cancelamento/erro/rede preservam os jobs; confirmacao retoma os mesmos registros.
- Checks/refreshs nao competem com login; regressao das corridas com pre-flight e
  retomada, snapshot de status, permissoes admin e recuperacao de erro cobertas.
- UI Playwright totalmente simulada: clique duplo vira um pedido, botoes bloqueados,
  fases/erro/confirmacao e estudos retomados aparecem pelo polling sem recarregar.
- Diagnostico real somente leitura: cookies presentes, token_fetch=false. Nenhum
  login/refresh foi disparado, nenhum estudo foi retomado nem houve envio real.
- Correcao ativa no servidor real; a nova entrada na conta depende do usuario no PC.

## Iniciador unico

- Testes isolados: reuso/identidade de PID, porta ocupada, FFmpeg/dependencias ausentes,
  timeout, saida precoce, ambiente do venv, HOME e URL configurados, logs separados,
  somente agente sem API e falha MQTT sem encerrar gravador.
- `--verificar` testado sem criar banco, logs ou processos de servico.
- Smoke real Windows com modulos falsos em pasta temporaria: processos ocultos,
  caminhos com espacos e `&`, dois iniciadores concorrentes, uma unica instancia,
  API pronta e agente reutilizado. Todos os processos falsos foram encerrados.
- BAT executado em copia preparada com `--verificar` e retorno zero.
- Diagnostico da instalacao real encontrou Python, bibliotecas do gravador/Drive/MQTT,
  FFmpeg/ffprobe, Node/rclone, destino, credenciais/token e caminhos do pipeline.
  Nao confirmou logins nem iniciou gravacao, filas ou conexao MQTT.

## Limites

Nao houve gravacao real, upload, envio WhatsApp ou comandos MQTT nesta validacao.
Nao foram executados Flutter test/build nem build da fonte Kotlin legada.
O conteudo de rede removido da fonte nao atualiza APK ja instalado.
Provas de captura na mesa, dois celulares, queda de conexao e reinicio controlado
continuam no `CHECKLIST.md`. Dependencias do pipeline externo nao foram modificadas.

## Revisao independente para consolidacao no GitHub

Codigo base `5c9549f`: suite repetida com Python 3.11.9/pytest 9.1.1 em copia
contendo apenas `app/`, `tests/`, `web/`, `config/default.json` e `pytest.ini`.
Nenhuma configuracao real, credencial, banco ou gravacao foi copiada. Foram
validados por parse 56 arquivos Python, sintaxe JS e XML/recursos Android.
Credenciais locais e padroes de tokens/chaves foram comparados com os 69 arquivos
incluidos/alterados no commit sem exibir valores; nenhum achado nessa varredura.

Limitacoes encontradas por inspecao e simulacoes: corrida login/pipeline (G01),
identidade entre instalacoes (G02) e texto legado de fallback (G03). Elas nao foram
corrigidas nesta consolidacao; ver `../CONTEXTO_AUDITORIA_PRODUTO.md`.
Os 309 testes verdes nao provam ausencia dessas falhas. Playwright/smoke Windows
acima sao evidencias anteriores e nao foram repetidos nesta revisao. Nenhuma
acao real de captura, login, upload, envio ou reinicio de servicos foi executada.

## Pacote pessoal - sprint 1

- Build real com Python embeddable 3.11.9, dependencias Python fixadas com SHA256,
  Node/FFmpeg/ffprobe privados, npm ci pelo lock e Chromium sem perfil.
- Smoke com PATH isolado: imports Python conferidos sob o runtime, PDF valido,
  ciclo XLSX, Chromium offline e CLI NotebookLM --version.
- Dependencias WhatsApp carregadas e require.resolve conferido dentro do pacote;
  NODE_PATH/NODE_OPTIONS externos removidos. Nenhuma conexao WhatsApp iniciada.
- FFmpeg executado com suporte DirectShow; MP3 de silencio sintetico gerado e
  validado pelo ffprobe, sem captura de microfone/mesa.
- --verificar passou sem criar config, banco ou logs; avisos de contas/destino
  ainda nao configurados sao esperados no pacote novo.
- 7.575 arquivos inventariados; fontes do app conferidas contra o pacote.
  Allowlist/varredura dos componentes do produto nao encontrou valores secretos
  locais nem copiou configuracao, banco, cookies, auth, QR ou gravacoes reais.
- A primeira extracao revelou MAX_PATH por raiz longa; ZIP foi corrigido para
  raiz fixa PregacaoRecorder/ e recebeu regressao. ZIP/SHA256 e extracao completa
  em caminho com espacos, acentos e & passaram; smoke completo repetido nessa copia.
- Entrada CMD corrigida para resolver a raiz antes de mudar o diretorio;
  Verificar Pacote.cmd passou na copia com espacos/acentos/& sem escrever config.
- Artefato e cache locais ignorados pelo Git; instrucoes em ../packaging/README.md.

Limites daquela sprint: nao reiniciou a instalacao em uso, nao renovou sessoes,
nao capturou audio real nem fez upload/envio. Windows limpo/outro PC e operacoes
com contas reais seguem na sprint 3. Instalador `.exe`, G01/G02 e configuracao
pessoal eram pendencias da sprint 2. Smoke nao comprova login Google ou entrega WhatsApp.

## Instalador e configuracao - sprint 2

- Suite final: 422 testes passaram em 34,02 s, em copia de fontes com home/bancos
  temporarios. Sintaxe JS e `git diff --check` passaram.
- Na primeira repeticao, um teste teve WinError 5 ao iniciar Node; passou isolado
  com Node do sistema e do pacote, e a suite final passou com o Node privado.
  A causa desse bloqueio nao foi comprovada. Apos o resumo final, uma thread de
  upload registrou erro ao acessar banco temporario ja removido no encerramento;
  pytest terminou com codigo zero, sem acesso ao banco real.
- G01: quatro regressoes com threads reais e processos simulados, incluindo
  clique apos a ultima guarda, Popen com falha e erro no monitor. A reserva do
  perfil dura ate o filho sair. Os casos de corrida falharam com o codigo anterior.
- G02: raiz/home absolutos na linha de comando; duas instalacoes, PID legado e
  divergente recusados. Processo sintetico real no Windows reutilizado sem duplicar;
  teste encerra somente o filho criado por ele. Nenhum PID real foi alterado.
- Bootstrap: segredo e ID persistentes, dois iniciadores concorrentes, PINs/config
  e identidade explicita preservados; homes do pacote isolados da origem;
  `--verificar` continua sem escrita de configuracao/banco/logs.
- UI: API de pareamento somente admin, sem senha do PC; token mascarado e
  limpeza ao sair. Chromium privado offline com APIs simuladas confirmou boot,
  login administrativo, ID/broker/porta/TLS, revelacao e reabertura sem erros JS.
- `packaging/smoke_installer.py`: 11 provas reais com pequenas fixtures publicas,
  mesma logica Inno e sem registro/atalho: instalacao com acentos/espacos/&, recusa
  pasta arbitraria, processo vivo, lock e junction, erro de backup antes da troca,
  reinstalacao/backup, recusa de uninstall com processo/lock e uninstall ocioso.
  Config/.env, SQLite com job em espera, audio e perfis sinteticos foram preservados.
- O smoke detectou Type Mismatch na data do backup; separadores corrigidos e as
  11 provas repetidas passaram. Backup nao duplica os audios preservados no destino.
- Na retomada, as 11 provas foram repetidas com sucesso em fixtures novas.
- Renovacao no pacote usa o perfil dedicado, com `--allow-headless --verify`;
  desenvolvimento preserva leitura de cookies do navegador configurado e fallback.
  Sucesso, falha, timeout, cadencia e preservacao dos jobs foram verificados.
- O extra opcional `rookie-cookies` foi retirado do lock (62 distribuicoes).
  Na conferencia do pacote anterior, seu modulo nativo desapareceu: as outras
  7.576 entradas e 52 fontes conferiam; causa da remocao nao comprovada.
  Nenhuma protecao do Windows foi alterada nem houve restauracao de quarentena.
- A revisao tambem detectou que NotebookLM abre contexto persistente headless
  sem canal explicito. O pacote anterior so incluia Chromium com canal; agora
  inclui tambem `chromium-headless-shell`. Os dois testes de cache novo falham
  com a implementacao anterior e passam com a correcao.
- Pacote completo final com 7.856 arquivos: smoke com Python/Node/FFmpeg/
  Chromium privados, perfil persistente headless sem canal, PDF, XLSX, versao e
  ajuda de login/refresh NotebookLM e MP3 sintetico/ffprobe; passou. O perfil
  headless foi novo, offline e removido ao terminar; nenhuma conta foi acessada.
  Fontes de bootstrap/UI e guia sincronizadas; manifesto registra snapshot
  de trabalho com alteracoes locais.
- Compilacao Inno 7.1.0 concluida: `dist-pacote/PregacaoRecorder-Instalar-sprint2-20261019T201816053366Z.exe`.
  SHA256 conferido no `.exe.sha256` adjacente; todos os hashes e 52 fontes/guia
  comparados com os arquivos finais. Nenhum arquivo extra ou dado real incluido.
- Varredura das fontes alteradas e dos 56 arquivos publicos do produto nao
  encontrou coincidencias com segredos locais. Dados/config reais continuam fora
  do inventario. Essa comparacao nao certifica historico Git ou codigo de terceiros.

Evidencias locais (ignoradas): `.bundle-cache/sprint2-final-validation.json`,
`.bundle-cache/ui-pairing-smoke.json`,
`.bundle-cache/ui-pairing-admin.png`, logs em `dist-pacote/` e
`%TEMP%/pregacao-installer-smoke-sj80ha67/smoke-report.json`.
Build e repeticao em [packaging/README.md](../packaging/README.md).

Limites: compilacao e execucao isolada neste Windows nao substituem Windows limpo
nem o PC destino. Nao houve novo login, captura real, upload, envio WhatsApp,
conexao MQTT ou reinicio do desenvolvimento. 2.2/2.3 exigem selecionar audio/disco,
autorizar contas, configurar ACL/credencial do novo ID e parear o celular no destino.
Essas provas operacionais permanecem junto do aceite da sprint 3.

## Edicao pessoal portatil no SSD (20/10/2026 UTC)

- Suíte completa: 491 testes passaram. Tres testes novos cobrem importacao,
  mudanca de pasta/letra, preservacao de credenciais e recusa de destino externo.
- Instalador privado Inno compilado, copiado com SHA-256 conferido para o SSD
  USB `E:` e executado com sucesso em `E:\PregacaoRecorder-Pessoal`. A pasta
  antiga `E:\PregacaoRecorder` nao foi modificada.
- Integridade antes do primeiro inicio: 7.859 arquivos publicos e 6.236
  privados conferidos por SHA-256. O banco copiado pelo backup SQLite passou
  em `integrity_check`; 12 sessoes, 12 uploads, 2 estudos, links de audio
  presentes apos realocacao para `E:`.
- Configuracao de Drive e `.env` originais preservados, segredo local de sessao
  criado, token Google e `storage_state.json` do NotebookLM identicos a origem,
  5.868 arquivos de autenticacao WhatsApp copiados. ID e broker MQTT coincidem
  com os defaults do APK, que contem os rotulos de iniciar/encerrar e conexao.
- `Verificar Pacote.cmd` no SSD passou com runtime privado, pasta de gravacoes,
  Drive e dependencias MQTT. O comando nao iniciou servicos nem gravou audio.
- O token Drive foi carregado como utilizavel pelo runtime do SSD e uma
  consulta somente leitura `about.get` ao Drive confirmou acesso real. O
  broker respondeu a TCP/TLS. Com token de operador copiado do SSD, um cliente
  MQTT temporario recebeu `avail`, `state`, `jobs` retidos e ACK positivo de
  `STATUS` do agente da origem, sem iniciar gravacao nem envio. A interface de
  audio configurada foi encontrada e duas
  capturas curtas consecutivas passaram; houve uma falha transitoria na
  primeira tentativa, sem gravacao persistida.
- O NotebookLM retornou autenticacao necessaria tanto na origem quanto no SSD.
  Leitura de cookies do Edge e renovacao pelo perfil headless nao recuperaram
  a sessao; falta login interativo e, se feito nesta maquina, refazer o
  instalador privado com o estado renovado.

Pendente no outro PC: testar driver/sinal de audio, gravacao real pelo PC e
celular, conexao MQTT efetiva, validade das sessoes de Drive/NotebookLM/
WhatsApp e envio com destinatario de teste. Uma sessao de navegador pode
precisar de novo login ao mudar de conta Windows.

## SSD limpo e APK conferido (20/10/2026, estado anterior)

- SSD USB `E:`: somente `PregacaoRecorder-Pessoal` permanece visivel como pasta
  de usuario na raiz. As duas pastas ocultas do Windows permanecem.
- A instalacao antiga tinha banco integro com zero sessoes, uploads e jobs.
  Seus nove MP3 ja existiam na instalacao pessoal com o mesmo SHA-256. A pasta
  antiga e os arquivos soltos foram movidos para arquivo privado ignorado em
  `recovery/ssd-root-archive-20261020/`; nenhum dado foi enviado ao Git.
- Instalador privado arquivado tem SHA-256 identico ao de `dist-pacote/`.
  Os 7.859 arquivos publicos da instalacao pessoal passaram novamente por
  SHA-256. `Verificar Pacote.cmd` passou apos a limpeza sem iniciar servicos.
- `flutter test`: 36 testes passaram. Um novo `flutter build apk --release`
  gerou arquivo com SHA-256 identico ao APK `2.6.0+12` do projeto e do SSD:
  `A986EC82AE37C10B9352B80684F0E3C5B27C213157E7BA953E285204498BA0C7`.
- Windows limpo, PC destino, controle pelo celular e sessoes externas ainda
  precisam de aceite real; NotebookLM segue exigindo login interativo.

## Reinstalacao do SSD (20/10/2026, estado anterior)

- `E:\PregacaoRecorder-Pessoal` nao estava presente quando o SSD foi revisto; a
  pasta antiga `E:\PregacaoRecorder` havia reaparecido incompleta. A origem da
  mudanca nao foi identificada. O instalador pessoal e seu `.exe.sha256` foram
  repostos na raiz do SSD. SHA-256 do `.exe`:
  `6EA5BE07A137EB7DDFC1BC3DA1E5A0053A2F9FAD4EBC0D00AE89BA4BEC15B48C`.
- O instalador foi executado a partir de `E:` com saida 0. `Verificar Pacote.cmd`
  saiu com 0. `verify_personal_portable.py` conferiu 7.859 arquivos publicos,
  6.236 privados e banco integro (12 sessoes, 12 uploads concluidos, 2 estudos
  concluidos). O primeiro inicio realocou config e caminhos historicos para `E:`.
- Diagnostico `app.launcher --verificar` com runtime privado saiu com 0: Python,
  FFmpeg/ffprobe, Node, MQTT, Drive e pipeline disponiveis. `rclone` opcional
  emitiu aviso com PATH restrito. `app.launcher --cli check` saiu com 0 e capturou
  2 segundos de sinal pelo microfone Logi C270 deste PC.
- O smoke privado passou imports, PDF, XLSX, Chromium, NotebookLM CLI,
  dependencias WhatsApp, DirectShow/FFmpeg e MP3 sintetico. O script encerrou
  com 1 somente na assercao final de pacote generico vazio: a edicao pessoal
  inclui intencionalmente config, dados e logs.
- O APK instalado mantem o SHA-256 do release `2.6.0+12` acima. Ao executar
  o iniciador do SSD na porta 8080, ele retornou 1 com a mensagem de porta
  ocupada e nao iniciou servicos. A copia de desenvolvimento esta ativa nessa
  porta; a abertura completa aguarda autorizacao para interromper essa copia
  temporariamente. A pasta antiga ainda aparece no SSD: a exclusao
  foi bloqueada por revisao automatica, e seu destino aguarda instrucao do usuario.

## Entrega final com SSD conectado (20/10/2026)

- Suite Python completa passou; Flutter concluiu 40 testes, `flutter analyze`
  nao apontou problemas e `node --check` passou. As duas referencias visuais
  da pagina principal foram atualizadas e revisadas. O APK release 2.7.0+13
  tem SHA-256 `CEC2A680D8738099F1FDEAA459B390B25D6F9789D2C6608922D0EEC1D889C0C1`.
  `apksigner` confirmou a mesma assinatura do APK anterior. O PIN nao e pedido
  no APK; credenciais/token MQTT continuam necessarios.
- Pacote publico `PregacaoRecorder-release-20261020T214011232587Z.zip`
  (7.861 arquivos inventariados e manifesto) passou o smoke dos runtimes;
  SHA-256 `5EC345E72E7204EE41839EF268C2A220E0684696E6F8D4B5560A397209B57CAF`.
  Instalador `PregacaoRecorder-Instalar-release-20261020T214011232587Z.exe`
  passou 11 provas isoladas de instalacao/reinstalacao/backup/recusa/remocao;
  SHA-256 `BF7F2233FAFF8DAD613D807338E8A07C318D64FF93AA783A00C6A4682CA8418D`.
  Instalador, ZIP, APK e sidecars foram copiados para a raiz do SSD `E:` e
  comparados por SHA-256 com a origem.
- A pasta pessoal estava na Lixeira do SSD, identificada pelos manifestos,
  banco e `portable-state.json`. Ela foi restaurada em
  `E:\PregacaoRecorder-Pessoal`; a pasta antiga permanece apenas na Lixeira.
  Antes da atualizacao havia 16 sessoes, 16 uploads concluidos, 6 jobs e 16
  gravacoes (13.769.525 bytes); SQLite `quick_check` retornou `ok`.
- O primeiro atualizador tentava substituir todos os arquivos, inclusive os
  identicos, e parou em arquivos do Playwright. A versao corrigida usa
  `Check: NeedsUpdate` com SHA-256 e atualizou o SSD. O log confirmou registro
  do inicio automatico com saida 0 e fechamento da instalacao; o processo Inno
  permaneceu ativo apos o log fechar e foi encerrado depois da validacao.
  Essa limpeza final do processo ainda merece teste no PC de destino; o
  conteudo instalado passou verificacao independente completa. Apos a correcao,
  os 24 testes de `tests/test_installer_builder.py` passaram, incluindo o
  inventario e os hashes gerados para o atualizador.
- Atualizador final:
  `PregacaoRecorder-Pessoal-Atualizar-update-20261020T222820Z.exe`, SHA-256
  `7F6BDE8C4E0348AD0B6BB1DDAD0D14984729862D023BB8CFB2076F2F5AC64025`.
  O manifesto instalado tem essa versao, 7.861 hashes publicos corretos, APK
  2.7 correto, os seis arquivos privados criticos inalterados antes da abertura,
  16 gravacoes com o mesmo total de bytes e banco integro. O diagnostico
  `app.launcher --verificar` do runtime no SSD saiu com 0.
- A abertura real do SSD iniciou gravador e agente, o painel respondeu HTTP
  200 com estado `IDLE` e mostrou programacao. Um cliente MQTT/TLS temporario
  recebeu `online` e estado retido; `STATUS` e `PREGACAO_LISTAR` tiveram ACK
  positivo, sem desconexao observada. Ao encerrar a instancia pessoal, o
  estado retido passou a `offline`. O laboratorio foi reiniciado em 8080,
  `IDLE`, com inicio automatico ativo. O inicio automatico pessoal foi
  desativado apenas neste PC; ha comandos no SSD para ativa-lo no outro PC.
  A abertura normal atualizou banco/config/token local sem perder as 16
  sessoes, 16 uploads, 6 jobs ou 16 gravacoes; `quick_check` continuou `ok`.
- Pendente no outro PC: testar driver e gravacao com audio real, instalar o APK
  nos dois celulares e confirmar a interface, concluir um estudo real e
  verificar o inicio apos nova entrada no Windows. Nenhuma mensagem WhatsApp
  foi enviada nesta entrega.

## Instalacao completa local a partir do SSD (21/10/2026)

- O instalador publico anterior nao levava contas nem dados e nao atendia ao
  uso sem SSD. O novo montador usa a pasta pessoal atual do SSD como origem
  privada e o pacote publico da mesma revisao como origem dos runtimes.
  O manifesto publico do SSD e o do pacote base tem 7.861 entradas identicas.
- A verificacao do SSD encontrou 32 arquivos publicos ausentes no driver do
  Playwright e nenhum arquivo presente com hash alterado. Os 32 foram repostos
  do pacote publico com hash conferido. Os backups de atualizacao continuam
  no SSD, fora do instalador completo.
- `pytest tests/test_personal_local_builder.py tests/test_portable_state.py
  tests/test_installer_builder.py -q`: 30 testes passaram. O teste inclui
  contas sinteticas, banco, gravacao, estado de erro encerrado, recusa de
  trabalho pendente e migracao de caminhos para outra pasta.
- Fixture Inno Setup 7 compilou, instalou arquivos publicos/privados com
  codigo 0 e recusou reinstalacao sobre a pasta usada (codigo 7), preservando
  seu arquivo privado. O instalador completo e a variante de prova compilaram.
- A variante completa de prova instalou em `D:\PRLT21` com codigo 0, sem
  registrar o autostart real deste PC. `verify_personal_portable.py` conferiu
  7.861 arquivos publicos e 6.263 privados. A realocacao deixou caminhos
  locais para 16 sessoes, 16 uploads e 6 jobs; todos os arquivos apontados
  existem. As 16 gravacoes estao presentes e SQLite `quick_check` retornou
  `ok`. `app.launcher --verificar` pelo runtime instalado saiu 0, inclusive
  com homes externos herdados apontados de proposito para uma unidade ausente.
- O script de inicio automatico, testado com pastas locais isoladas, registrou
  um atalho de prova e resolveu a copia local sem o SSD. O instalador real foi
  copiado para a raiz do SSD e o SHA-256 coincide com a origem:
  `FB6DC3C0028DF480C02A4438C0C3144A7EC32DF76919C0C86E1AB7ED37FFE0FC`.
- Pendente no novo PC: instalacao real, abertura sem SSD, driver de audio,
  validade das sessoes dos provedores e teste com os dois celulares. Nao foi
  feito envio WhatsApp nem estudo real.
- As copias de `PregacaoControle-2.7.apk` na raiz e na pasta pessoal do SSD
  foram reconferidas em 21/10/2026: ambas tem SHA-256
  `CEC2A680D8738099F1FDEAA459B390B25D6F9789D2C6608922D0EEC1D889C0C1`.
  O ajuste posterior foi somente no instalador Windows; nenhum novo APK foi
  compilado ou instalado nos celulares neste ciclo.
