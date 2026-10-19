# PR-DIST-001 - Instalar meu Pregacao Recorder em outro PC

Estado: sprint 1 implementada em ZIP de teste; aceite em Windows limpo/destino pendente. Escopo pessoal confirmado em 19/10/2026.
Uso pessoal, Windows 10/11 x64. Este plano substitui integralmente o plano anterior de oito sprints.

## Objetivo

Entregar um instalador simples para o proprio usuario instalar e executar o
programa em outro PC, com as funcionalidades atuais. O pacote leva gravador,
painel, agente MQTT, pipeline e dependencias; nao exige preparar ambiente de
desenvolvimento. Usar as telas de configuracao existentes e um guia curto.

## Funcionalidades que precisam continuar funcionando

- Gravacao DirectShow, teste de audio, segmentos, MP3 e recuperacao ja existente.
- Escolha de pasta/disco, historico, configuracoes, cadastro de pregacoes e importacao CSV/XLSX.
- Google Drive: conectar conta, escolher pasta e enviar pela fila atual.
- NotebookLM: verificar/renovar login e gerar o estudo pelo pipeline atual, preservando o prompt.
- Geracao de PDF e envio pelo WhatsApp para o destinatario configurado.
- Controle pelo celular atual via MQTT, com comandos, estado e progresso existentes.

Preservar o comportamento atual de filas/retentativas. Nao prometer novos
checkpoints, retomada por etapa ou funcionalidades que hoje estao incompletas.

## Solucao simples

- Instalar por usuario em `%LOCALAPPDATA%\PregacaoRecorder`, com pastas do gravador, pipeline e runtimes.
- Manter essas pastas gravaveis e os layouts atuais sempre que possivel; nao exigir uma refatoracao geral de codigo/dados ou do banco.
- Usar Python, FFmpeg, Node e pacotes necessarios do proprio pacote. Criar ambientes no destino se forem usados; nao copiar a `.venv` deste PC com remendos.
- Incluir o navegador necessario ao NotebookLM ou provisiona-lo pela instalacao; nao depender de uma instalacao oculta neste PC.
- Um instalador `.exe` e um atalho para abrir o programa. Reaproveitar `iniciar-tudo.bat`/launcher e CONFIG existentes.
- Reutilizar as mesmas contas/servicos do usuario. No destino, selecionar interface/pasta e fazer login Google/NotebookLM ou pareamento WhatsApp quando solicitado.
- Instalador versionado sem dados pessoais no GitHub. Configuracoes reais podem ser transferidas separadamente e em privado; cookies/perfis nao sao considerados automaticamente transportaveis.
- Instalacao nova com banco/historico novos e as mesmas funcoes. Transferir historico/gravacoes antigos e opcional; nao criar um migrador para isso nesta tarefa nem alterar dados do PC de origem.

## Sprint 1 - Montar o pacote completo

- [x] PR-DIST-001.1.1 Reunir gravador/web/agente e somente os arquivos do pipeline usados pelo programa; preservar prompt e registrar versoes/componentes incluidos.
- [x] PR-DIST-001.1.2 Incluir runtimes e dependencias nas versoes compativeis: Python, FFmpeg, NotebookLM/Playwright/navegador, PDF, Node/WhatsApp e `openpyxl`. Corrigir manifestos incompletos; gerar pacote sem instalar ferramentas manualmente no destino.
- [x] PR-DIST-001.1.3 Resolver caminhos a partir da pasta instalada, incluindo executaveis, defaults, assets e pastas do pipeline. Nao depender de `D:\Dev`, pasta pessoal ou PATH do PC original.
- [x] PR-DIST-001.1.4 Preparar instalador privado sem `.env`, tokens, cookies, QRs, banco ou gravacoes reais nos artefatos enviados ao GitHub.

Detalhes ja identificados: manifesto externo declara `notebooklm`, mas o ambiente
observado usa `notebooklm-py`; `openpyxl` falta no manifesto do gravador. O pipeline
pressupoe `.venv/Scripts`; Node/Baileys precisa de conjunto compativel. `rclone`
nao e necessario ao fluxo integrado chamado com `--skip-drive`. Nao incluir os
gravadores/bandejas antigos do pipeline nem ferramentas sem uso nesse caminho.

Aceite: em ambiente Windows limpo, os componentes locais funcionam com os
runtimes do pacote, sem Python/Node/FFmpeg/Git/SDK previamente instalados.

## Resultado implementado da sprint 1 (19/10/2026)

- Pipeline minimo incorporado em `vendor/sermon-pipeline/`, com prompt identico e configuracao publica de exemplo; fonte externa e dados reais preservados.
- Montador local em `packaging/build_bundle.py`; Python 3.11.9 privado, 63 distribuicoes Python com hashes, Node 24.18.0, FFmpeg/ffprobe e Chromium incluidos.
- Launcher reconhece o pacote; caminhos/perfil/CLI NotebookLM usam os componentes locais. Desenvolvimento continua usando `.venv` e configuracao existentes.
- ZIP local em `dist-pacote/PregacaoRecorder-sprint1-20261019T142634742522Z.zip` (cerca de 479 MiB); raiz interna curta `PregacaoRecorder/`. Artefato/cache ignorados pelo Git.
- 350 testes passaram em copia isolada. Smoke real: imports de origem privada, PDF, XLSX, Chromium offline, NotebookLM --version, dependencias Node locais, DirectShow e MP3 sintetico/ffprobe; diagnostico sem escrita.
- Allowlist/varredura sem configuracao pessoal, cookies, tokens, banco ou gravacoes. ZIP corrigido extraido em caminho com espacos, acentos e &: smoke completo repetido com sucesso.
- Instrucoes: [packaging/README.md](../packaging/README.md). O pacote e de teste; `.exe`, configuracao pessoal e G01/G02 ficam na sprint 2; Windows limpo, audio e contas reais no destino continuam na sprint 3.

## Sprint 2 - Instalar e configurar para meu uso

- [ ] PR-DIST-001.2.1 Criar instalador com pasta gravavel, atalho unico e inicializacao dos mesmos processos; repetir a instalacao preserva configuracoes/dados, com copia de seguranca simples antes de substituir arquivos.
- [ ] PR-DIST-001.2.2 Ajustar audio, destino, caminhos do pipeline, contas e destinatario usando CONFIG e um guia curto. Reaproveitar preferencias/PINs quando desejado; gerar segredo local se faltar, sem reformular autenticacao ou criar novo assistente.
- [ ] PR-DIST-001.2.3 Configurar MQTT para o mesmo celular. Se os dois PCs puderem ligar, usar identidade diferente no novo PC, ajustar o pareamento e conferir acesso aos novos topics no broker; so preservar a identidade antiga ao substituir o PC anterior.
- [ ] PR-DIST-001.2.4 Aplicar os ajustes pequenos de inicializacao/login necessarios: G01 (login/pipeline concorrentes) e G02 (PID herdado ou de outra instalacao). Nao encerrar processos nao identificados nem copiar PIDs de origem.
- [ ] PR-DIST-001.2.5 Preservar dados existentes, gravacao sem internet e regras atuais de armazenamento. Corrigir outro defeito somente se reproduzido como impedimento ao uso das funcoes atuais no pacote.

Aceite: instalar, abrir pelo atalho, selecionar audio/pasta e conectar as mesmas
integracoes sem editar caminhos manualmente. PINs continuam funcionando; dados
de origem permanecem intactos e o iniciador nao cria processos duplicados.
Nao criar contas de terceiros nem enviar para destinatario nao conferido.

## Sprint 3 - Testar no outro PC e entregar

- [ ] PR-DIST-001.3.1 Instalar em Windows limpo, depois conferir no PC destino: atalho, caminho com espacos/acentos, porta e permissao de escrita; diagnostico local sem executar filas.
- [ ] PR-DIST-001.3.2 Validar gravacao real, MP3 audivel, historico, troca de destino, recuperacao atual, cadastro/importacao CSV/XLSX e configuracoes; gravar localmente sem internet.
- [ ] PR-DIST-001.3.3 Validar Drive, login NotebookLM, estudo/PDF e WhatsApp com conta/destinatario de teste definidos pelo usuario. Testar controle/progresso pelo celular atual e reabertura do programa.
- [ ] PR-DIST-001.3.4 Entregar instalador e guia curto com o que selecionar/conectar no destino. Registrar defeitos impeditivos corrigidos e qualquer teste real ainda pendente.

Aceite final: o proprio usuario instala e executa todas as funcionalidades acima
no outro PC sem depender deste. Testes automatizados relevantes acompanham as
alteracoes; a base anterior de 309 testes nao substitui as provas no destino.
Driver/permissao da interface de audio precisa estar disponivel. Integracoes
continuam precisando de internet e login; a gravacao local nao.

## Removido deste projeto de melhorias

- Distribuicao publica/comercial, multiusuario, provisionamento de clientes e novo modelo de permissoes.
- Novo assistente completo, servico Windows, assinatura publica de instalador e nova distribuicao/assinatura do APK.
- CI de release, multiplas plataformas/arquiteturas e matriz extensa de computadores; manter teste limpo e no PC destino.
- Atualizador automatico, rollback, migrador entre PCs e sistema novo de backup. Basta copia de seguranca e reinstalacao cuidadosa com processos ociosos.
- Novos checkpoints/idempotencia do pipeline, nova interface de jobs e reformulacao das filas.
- Novos formularios Flutter, metadados no estudo/PDF e correcoes gerais sem relacao com a instalacao ou regressao das funcoes atuais.

Os achados da [auditoria](../CONTEXTO_AUDITORIA_PRODUTO.md) continuam registrados;
retira-los destas sprints nao significa que foram corrigidos. O APK atual sera
reutilizado; so alterar sua fonte se houver incompatibilidade comprovada.

Arquivos envolvidos: `app/launcher.py`, `app/paths.py`, `app/config.py`,
`app/estudos.py`, resolucao de ferramentas de audio, manifests e arquivos do
pipeline; novos arquivos de empacotamento e testes apenas onde necessario.

Proximo passo: sprint 2, criar o instalador `.exe` a partir do pacote e preparar
configuracao pessoal/ajustes de inicio e login. O aceite final depende da sprint 3;
a existencia do ZIP e do smoke local nao comprova funcionamento no outro PC.
