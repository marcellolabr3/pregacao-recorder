# PR-DIST-001 - Distribuicao instalavel do Pregacao Recorder para Windows

Estado: planejada; implementacao nao iniciada. Criada em 19/10/2026 a pedido do usuario.
Base verificada: commit `396240a`; 309 testes Python aprovados na revisao anterior.
Objetivo: instalar o produto completo em outro PC compativel sem preparar um ambiente de desenvolvimento.

## Resultado esperado e limites

Entregar um instalador Windows com gravador, agente MQTT, pipeline de estudos e
suas dependencias. O operador instala, escolhe audio/destino, conecta suas contas
e usa o programa pelo mesmo painel. O PC de origem deixa de ser um requisito.

- Alvo inicial: Windows 10/11 x64; registrar builds efetivamente homologadas. Outros sistemas/arquiteturas ficam fora desta entrega.
- Instalacao por usuario, sem exigir Python, Node, FFmpeg, Git, Flutter ou Android SDK preinstalados.
- O instalador completo deve trazer os componentes de execucao; builds podem baixar dependencias verificadas. Nao depender de `pip install`/`npm install` na internet do cliente.
- Audio local deve funcionar sem internet. Drive, NotebookLM, WhatsApp e MQTT precisam de conectividade e contas/servicos validos.
- Drivers da interface de audio e permissoes do Windows continuam requisitos do equipamento; detectar e orientar quando faltarem.
- Instalar em outro PC nao transfere automaticamente contas, sessoes autenticadas, dados ou licencas de terceiros.
- Esta tarefa registra o plano. Criar este documento nao instala ferramentas, modifica o pipeline, renova login ou executa envios.

## Diagnostico que fundamenta a tarefa

| Area | Estado confirmado | Trabalho necessario |
|---|---|---|
| Gravador | BAT exige `.venv`; ferramentas sao descobertas no PATH; `requirements.txt` usa intervalos amplos. | Runtime privado, dependencias fixadas e resolucao controlada de executaveis. |
| Dados | `app/paths.py` mistura codigo e dados; `Config.defaults_file` busca defaults sob o home. | Separar recursos imutaveis de configuracoes/banco/dados gravaveis. |
| XLSX | `openpyxl` e usado, mas nao consta do manifesto do gravador (D08). | Declarar e incluir a dependencia; provar importacao em ambiente limpo. |
| Pipeline | Pasta externa sem `.git`; `pipeline.py` aponta para `.venv/Scripts`, escreve junto ao codigo e depende de outros componentes. | Versionar somente os componentes necessarios e incluir sua versao no release. |
| Manifesto externo | Declara `notebooklm`, enquanto o ambiente observado tem `notebooklm-py==0.8.5`. | Corrigir nome/distribuicao e resolver versoes em ambiente limpo; nao congelar cegamente o ambiente inteiro deste PC. |
| PDF/WhatsApp | Pipeline usa Markdown/xhtml2pdf e Node/Baileys/qrcode. Baileys observado e ESM, com requisito Node >=20; `send.js` usa `require`. | Fixar e provar conjunto compativel de Python/Node/dependencias, inclusive extensoes nativas. |
| Navegador | Login usa Playwright com canal de navegador; perfis padrao ficam fora do produto. | Escolher navegador/canal suportado e provisionar/verificar; definir home de sessao exclusivo do produto. |
| Controle Android | Flutter 2.6.0+12 e fonte atual; Kotlin 1.4 e legado. Receita Flutter de release ainda usa assinatura debug. | Uma distribuicao oficial, assinatura e compatibilidade com APKs existentes verificadas. |
| Instalacao | Nao ha instalador/release Windows reproduzivel; migrador antigo remenda venvs/EXEs e copia perfis. | Instalacao nova, transferencia, atualizacao e reparo com fluxos proprios. |

Contrato atual: gravador chama `PYTHON pipeline.py AUDIO --skip-drive [--to NUMERO]`
e interpreta marcadores de texto do log. Drive e estudo rodam em filas separadas.
`rclone` e opcional no fluxo integrado, pois o gravador ja faz upload pela API Python.
Nao incluir os gravadores/bandejas antigos do pipeline, Tailscale ou outras
ferramentas sem uso nesse contrato. Inventario final ainda precisa ser homologado.

## Arquitetura proposta para a distribuicao

- Aplicacao/runtimes versionados: `%LOCALAPPDATA%\Programs\PregacaoRecorder`.
- Dados por usuario: `%LOCALAPPDATA%\PregacaoRecorder` (configuracao, SQLite, sessoes, logs e gravacoes padrao).
- Preservar pasta externa de gravacoes escolhida pelo operador e o override `PREGACAO_HOME`.
- Defaults e assets web pertencem ao pacote; configuracao do usuario fica nos dados. Apenas trocar HOME hoje perderia defaults.
- Fornecer Python privado com dependencias preparadas ou executaveis em diretorio: a prova da sprint 1 escolhe e registra o formato. O instalador final e um unico `.exe`.
- Nao copiar a `.venv` existente, remendar caminhos binarios nem usar o migrador legado como instalador. Se a solucao usar venv, recria-la no destino com runtime privado e pacotes locais fixados.
- Manter processo de captura independente de MQTT/internet/pipeline. Atalho unico e opcao de iniciar apos login no Windows.
- Fonte/versao do pipeline controladas pelo produto; preservar o prompt existente. Nao iniciar `tray_app`/`recorder` externos.
- Pacote generico sem `.env`, tokens, cookies, perfis, QRs autenticados, banco, gravacoes ou configuracao pessoal deste PC.

## Sequencia e marcos

| Sprint | Entrega | Dependencia | Marco |
|---|---|---|---|
| 1 | Inventario e build reproduzivel | Nenhuma | Arquitetura e dependencias comprovadas |
| 2 | Correcoes da base existente | 1 para matriz de testes | Base preparada para distribuicao |
| 3 | Runtime independente e caminhos | 1 e 2 | Produto executa fora da arvore de desenvolvimento |
| 4 | Instalador e primeiro acesso | 3 | Primeiro instalador candidato, ainda nao homologado |
| 5 | Recuperacao das filas/pipeline | 1 e 2; pode avancar junto de 3/4 | Resiliencia necessaria ao fluxo completo |
| 6 | Backup, transferencia e atualizacao | 3, 4 e contratos de persistencia da 5 | Instalacao pode evoluir sem perder dados |
| 7 | Homologacao, APK e release | 2 a 6 | Liberacao para outros PCs |
| 8 | Funcionalidades restantes | Contratos estabilizados | Evolucao funcional apos distribuicao |

As sprints sao pacotes de trabalho, sem estimativa de prazo ainda. A duracao da
sprint 5 depende da integracao do pipeline externo. Nenhuma sprint esta concluida
apenas por existir codigo no PC atual. Um candidato da sprint 4 nao e o release final.

## Sprint 1 - Inventario e reproducibilidade

- [ ] PR-DIST-001.1.1 Inventariar fontes, bibliotecas, executaveis, navegadores, extensoes nativas, arquitetura, licencas e requisitos de rede realmente usados.
- [ ] PR-DIST-001.1.2 Incorporar/versionar o pipeline necessario ou definir artefato/dependencia imutavel com hash e versao. Retirar dependencia de pasta pessoal e preservar prompt.
- [ ] PR-DIST-001.1.3 Corrigir manifesto NotebookLM; criar locks resolvidos Python/Node, incluindo `openpyxl`, PDF, Playwright e dependencias WhatsApp. Separar dependencias de teste/build/runtime.
- [ ] PR-DIST-001.1.4 Provar Python/Node/Baileys compativeis em ambiente vazio; incluir estrategia para extensoes sem compilador no cliente.
- [ ] PR-DIST-001.1.5 Prototipar formato de runtime privado/empacotamento e navegador. Registrar decisao com tamanho, inicializacao, subprocessos, auth e atualizacao verificados.
- [ ] PR-DIST-001.1.6 Criar manifesto de release com versoes do gravador, pipeline, protocolo, runtimes e dependencias; downloads somente de fontes definidas, com integridade verificada.

Arquivos envolvidos: `requirements.txt`, `app/estudos.py`, manifests/fontes do
pipeline externo e novos arquivos previstos em `packaging/`, locks e automacao de build.

Aceite: duas preparacoes limpas do mesmo conjunto fixado produzem inventario igual
e hashes registrados para cada artefato; imports/CLI/PDF/WhatsApp simulado funcionam
sem aproveitar site-packages, PATH, perfil ou instalacoes pessoais. Nao e exigido
hash identico dos instaladores se ferramentas inserirem timestamps; registrar essa diferenca.

## Sprint 2 - Corrigir defeitos da base existente

- [ ] PR-DIST-001.2.1 G01: coordenar login e pipeline durante toda a transicao de inicio, incluindo clique apos a guarda; regressao com concorrencia simulada.
- [ ] PR-DIST-001.2.2 G02: vincular PID a instalacao/home e identidade do processo, considerando reutilizacao de PID; testar duas copias com o mesmo Python base.
- [ ] PR-DIST-001.2.3 D09/D10: proteger audios referenciados por upload/estudo/reprocessamento antes de qualquer retencao ou exclusao apos upload.
- [ ] PR-DIST-001.2.4 D11: validar a configuracao inteira antes de persistir/aplicar; rejeicao nao pode deixar valores parcialmente alterados.
- [ ] PR-DIST-001.2.5 D01-D07: validar cadastro/edicao/importacao no servidor; lote transacional, controle de versao, PATCH parcial e duplicatas consistentes. Aceitar `.xlsx` ou implementar explicitamente `.xls`.
- [ ] PR-DIST-001.2.6 D14: escapar dados de banco/API nas insercoes HTML; cobrir campos de programacao e integracoes.
- [ ] PR-DIST-001.2.7 G03: corrigir texto/comentarios que prometem troca automatica de disco; alinhar legado com captura bloqueada se destino faltar.

Arquivos: `app/estudos.py`, `app/launcher.py`, `app/upload/queue.py`,
`app/storage/layout.py`, `app/api/routes.py`, `app/importacao.py`, `app/db.py`,
`web/`, textos Kotlin legados e testes pertinentes.

Aceite: regressoes isoladas cobrem os defeitos; lote invalido nao deixa gravacao
parcial, edicao concorrente retorna conflito, limpeza preserva audio necessario,
configuracao rejeitada nao muda estado e login/pipeline nao disputam a sessao.
Manter cobertura util da base de 309 testes, adaptando-a quando o contrato mudar.

## Sprint 3 - Runtime independente e separacao de caminhos

- [ ] PR-DIST-001.3.1 Implementar separacao entre raiz da aplicacao, defaults/assets e dados; resolver home antes dos singletons/banco/logs.
- [ ] PR-DIST-001.3.2 Resolver Python, NotebookLM, FFmpeg e Node por caminhos controlados; PATH alterado somente nos filhos quando necessario.
- [ ] PR-DIST-001.3.3 Adaptar inicio dos filhos ao formato escolhido; nao presumir que `sys.executable -m` serve para um executavel congelado.
- [ ] PR-DIST-001.3.4 Refatorar pipeline para config/logs/output/temporarios e `whatsapp/auth` fora do codigo. Usar home/perfil NotebookLM exclusivo do produto em login, probe e processamento.
- [ ] PR-DIST-001.3.5 Empacotar assets web, defaults, prompt, bibliotecas e navegador conforme a decisao da sprint 1; nao incluir componentes sem uso.
- [ ] PR-DIST-001.3.6 Diagnostico distingue captura local disponivel de integracao nao configurada; verifica versoes e caminhos sem criar banco, iniciar filas ou exibir segredos.

Arquivos: `app/paths.py`, `app/config.py`, `app/main.py`, `app/launcher.py`,
`app/cli.py`, `app/audio/`, `app/recording/consolidate.py`, `app/estudos.py`,
fontes do pipeline e novos scripts de build.

Aceite: pacote executa com cwd arbitrario, caminho com espacos/acentos e fontes
sem escrita; usa seus runtimes mesmo com versoes conflitantes no PATH. Nova
instalacao nao procura `D:\Dev`, pasta de Aska ou ferramentas globais.
Captura/painel funcionam sem rede; dados existentes e override continuam suportados.

## Sprint 4 - Instalador e assistente de primeiro acesso

- [ ] PR-DIST-001.4.1 Criar instalador por usuario com atalho unico, diagnostico/reparo e registro da versao instalada; impedir duas instalacoes acidentais sobre os mesmos dados.
- [ ] PR-DIST-001.4.2 Assistente para interface de audio, teste explicito de sinal, destino, espaco livre e permissoes; nao capturar sem acao do operador.
- [ ] PR-DIST-001.4.3 D15: gerar segredo de sessao aleatorio persistente; iniciar instalacao nova em loopback. Acesso LAN opt-in com autenticacao configurada; nao abrir firewall/roteador automaticamente.
- [ ] PR-DIST-001.4.4 Google Drive: configurar cliente OAuth/conta/pasta e fluxo de consentimento com requisitos documentados; NotebookLM: login acompanhado no perfil do produto. Sessao ausente nao impede gravacao local.
- [ ] PR-DIST-001.4.5 WhatsApp: pareamento e destinatario confirmados pelo operador; desativado ate configurar. Impedir fallback silencioso para numero herdado do pipeline.
- [ ] PR-DIST-001.4.6 MQTT: cadastrar broker/TLS/credenciais e ID persistente unico em instalacao nova; explicar provisionamento/ACL por aparelho. Hostname novo nao deve trocar topics.
- [ ] PR-DIST-001.4.7 Registrar instalacao nova e transferencia como fluxos distintos; nunca clonar perfis deste PC no pacote generico. Configuracoes existentes nao sao substituidas pelo assistente.

Arquivos: novo instalador em `packaging/`, `app/config.py`, `app/api/auth.py`,
`app/api/routes.py`, `app/remote/agent.py`, `web/` e exemplos/guias.

Aceite: usuario instala e abre painel sem terminal, `pip`, SDK ou edicao manual de
caminhos. Reinicio preserva segredo/identidade; contas nao configuradas aparecem
como pendentes; nao ha envio para numero nao confirmado. LAN e acesso admin tem
protecao explicita. Instalador e testado sem dependencias globais e sem rede para instalar/gravar.

## Sprint 5 - Recuperacao de filas e processamento

- [ ] PR-DIST-001.5.1 C07/C08: contrato versionado/estruturado entre gravador e pipeline, com checkpoints e identificadores de notebook/fonte/relatorio/PDF ja produzidos.
- [ ] PR-DIST-001.5.2 C09-C11: persistir estado/tentativa/identificador do envio WhatsApp; retry somente do PDF e intervencao especifica. Envio ambiguo nao deve disparar repeticao cega.
- [ ] PR-DIST-001.5.3 C12/C13: persistir sessao de upload quando suportado, tratar expiracao e reconciliar confirmacao ambigua com identidade estavel antes de criar outro arquivo.
- [ ] PR-DIST-001.5.4 C14/C16: estado explicito de espera e operacao minima por job (ver motivo, retomar etapa permitida, retry/cancelamento seguro).
- [ ] PR-DIST-001.5.5 D12/D13: distinguir processo agente ativo de conexao real ao broker; saude WhatsApp baseada em sessao atual/checagem apropriada, sem envios de teste automaticos.
- [ ] PR-DIST-001.5.6 C15: Flutter descarta progresso retido/antigo por sequencia e contexto do job; testar reconexao e troca de job.

Arquivos: `app/estudos.py`, `app/db.py`, `app/upload/drive.py`,
`app/upload/queue.py`, `app/remote/agent.py`, APIs/UI, Flutter e pipeline/WhatsApp.

Aceite: interromper depois de cada etapa e reiniciar em testes controlados;
retomar do checkpoint com mesmos registros/artefatos. Simular resposta perdida
apos Drive/WhatsApp aceitar: reconciliar ou pedir intervencao sem duplicacao cega.
Nao prometer entrega final WhatsApp nem garantia de envio unico quando o servico
nao permitir comprovar. Falha de MQTT/estudo nunca encerra gravacao local.

## Sprint 6 - Backup, transferencia, atualizacao e desinstalacao

- [ ] PR-DIST-001.6.1 Versionar schema/config e migracoes nao destrutivas; backup SQLite consistente por API apropriada, considerando WAL, mais manifesto dos arquivos.
- [ ] PR-DIST-001.6.2 Transferencia para outro PC preserva sessoes/jobs/IDs e remapeia somente caminhos de arquivos transferidos; validar audios e resultados antes de liberar filas.
- [ ] PR-DIST-001.6.3 Preservar `device_id` efetivo em transferencia (inclusive derivado do hostname antigo) e refazer logins quando necessario. Transferencia pressupoe PC antigo desativado para processamento.
- [ ] PR-DIST-001.6.4 Instalacao independente recebe nova identidade/pareamento; nao duplicar jobs pendentes para dois PCs consumirem. Dados e backup com segredos nao entram no instalador publico.
- [ ] PR-DIST-001.6.5 Atualizar apenas quando captura, conversao, upload, login e estudo estiverem ociosos; preparar/verificar arquivos antes da troca, com recuperacao de interrupcao.
- [ ] PR-DIST-001.6.6 Testar rollback compativel de codigo e banco; nao restaurar cegamente schema antigo sobre dados novos. Preservar backup verificavel e impedir downgrade incompativel.
- [ ] PR-DIST-001.6.7 Reparo preserva dados. Desinstalacao preserva dados por padrao; exclusao definitiva e uma acao separada explicita. Diagnostico exportavel remove segredos.

Arquivos: instalador/updater/migrador novos, `app/db.py`, `app/paths.py`,
`app/launcher.py`, recuperacao, contratos do pipeline e documentacao.

Aceite: backup/restauracao validos; teste de upgrade da versao anterior, reparo,
interrupcao em cada fase e retorno a versao compativel. Credenciais, audios,
segmentos, IDs, estados e destino externo preservados. Mudanca de usuario/PC nao
presume que cookies ou protecao vinculada ao Windows sejam transportaveis.

## Sprint 7 - Homologacao em PC limpo e distribuicao oficial

- [ ] PR-DIST-001.7.1 Automatizar build/teste em Windows limpo a partir das fontes/locks, incluindo instalacao, primeira abertura, reparo e upgrade; registrar versao/arquitetura de cada artefato.
- [ ] PR-DIST-001.7.2 Homologar em VM sem Python/Node/FFmpeg/Git e em um segundo PC fisico; testar usuario comum, espacos/acentos, porta ocupada, falta de disco/espaco e ferramentas conflitantes.
- [ ] PR-DIST-001.7.3 Audio real: selecionar mesa/interface, gravar, ouvir MP3 e recuperar interrupcao preparada; desconectar destino impede captura sem troca automatica.
- [ ] PR-DIST-001.7.4 E2E com contas/destino de teste: Drive, login NotebookLM expirado, estudo/PDF, WhatsApp, falta de internet, dois celulares, reconexao e reinicio durante processamento.
- [ ] PR-DIST-001.7.5 Flutter oficial: inventariar certificado/versionCode dos APKs em uso, definir assinatura de release e migracao sem perder configuracao. Kotlin permanece legado identificado. Executar analyze/test/build e validar compatibilidade MQTT.
- [ ] PR-DIST-001.7.6 Entregar instalador, APK compativel, manifesto, checksums, notas e procedimento de atualizacao. Definir estrategia de assinatura Windows antes de distribuicao publica; manter chaves fora do codigo/pacotes.
- [ ] PR-DIST-001.7.7 Manual com capturas reais: instalar, configurar contas, gravar, recuperar, atualizar e pedir suporte; publicar limitacoes comprovadas e evidencias de QA.

Arquivos previstos: automacao Windows em `.github/workflows/`, `packaging/`,
Flutter/Gradle, testes de instalacao e guias. Builds nao devem usar credenciais reais.

Aceite final: outra pessoa instala a mesma versao num segundo PC sem depender do
PC original, completa configuracao guiada e executa fluxo local e integrado;
atualiza/restaura sem perder dados. Testes automatizados e provas reais registrados.
A assinatura do APK instalado deve ser considerada antes de mudar a chave; se
atualizacao direta nao for possivel, documentar transferencia de configuracao.
Sem hardware/contas de teste disponiveis, marcar a homologacao pendente e nao
apresentar apenas testes simulados como prova de produto pronto.

## Sprint 8 - Evolucao funcional apos a distribuicao

- [ ] PR-DIST-001.8.1 C01/C02: formulario/CRUD de pregacoes no Flutter e comandos MQTT implementados no agente, com mesmas validacoes do servidor.
- [ ] PR-DIST-001.8.2 C03-C06: associar gravacao a programacao explicitamente, congelar snapshot na gravacao e enviar metadados ao estudo/PDF por contrato versionado.
- [ ] PR-DIST-001.8.3 C16: completar painel de jobs web/mobile alem do minimo de recuperacao da sprint 5; estado de cada etapa, historico e acoes permitidas.
- [ ] PR-DIST-001.8.4 Atualizar manual/PDF/promessas do produto somente apos testes dos fluxos novos.

Aceite: cadastro real em dois clientes com conflito tratado; gravacao atrasada
continua ligada a pregacao selecionada; edicao futura nao muda snapshot ja gravado;
PDF exibe metadados corretos e telas nao prometem recursos ausentes. Esta sprint
nao bloqueia o primeiro release se esses recursos forem declarados ausentes.

## Rastreabilidade das pendencias existentes

| Pendencias da auditoria | Sprint |
|---|---|
| G01, G02, G03; D01-D07, D09-D11, D14 | 2 |
| D08 e F09 (dependencias/pipeline) | 1 e 3 |
| D15 (primeiro acesso) | 4 |
| C07-C14; D12/D13; C15; C16 minimo | 5 |
| Atualizacao/migracao/dados e reinstalacao | 6 |
| F05/F07/F08 e entrega de artefatos | 7 |
| C01-C06 e C16 completo | 8 |
| Retirada Raspberry e iniciador unico; A01-A08/A10/B/D16 | Ja implementados; preservar por regressao, sem reabrir como trabalho novo |
| A09 (login real) | Fluxo em 2/4; comprovacao com conta de teste em 7 |

## Referencias tecnicas verificadas

- Codigo/manifests atuais e [auditoria do projeto](../CONTEXTO_AUDITORIA_PRODUTO.md).
- [Python venv](https://docs.python.org/3.11/library/venv.html): ambientes usam caminhos absolutos e devem ser recriados ao mudar de local.
- [Python no Windows - distribuicao embarcada](https://docs.python.org/3.11/using/windows.html#the-embeddable-package): instalador da aplicacao deve prover dependencias; nao tratar a distribuicao embarcada como Python comum com pip.
- [Playwright - navegadores](https://playwright.dev/python/docs/browsers): escolher/provisionar navegador e versao compativeis, sem presumir que instalar a biblioteca instala o canal Edge/Chrome.
- [Android - assinatura](https://developer.android.com/studio/publish/app-signing): planejar assinatura e continuidade das atualizacoes do aplicativo existente.

Proximo passo concreto: executar PR-DIST-001.1.1 a 1.6 e produzir a prova limpa
com manifesto/decisao de empacotamento; depois atacar as correcoes da sprint 2.
