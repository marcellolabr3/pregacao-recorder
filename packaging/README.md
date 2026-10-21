# Pacote e instalador pessoal Windows

Monta o pacote completo e o instalador `.exe`, com gravador, pipeline e runtimes
privados. Nao inclui contas ou dados pessoais. Configuracao e pareamento no
destino: [guia curto](../docs/GUIA_INSTALACAO_WINDOWS.md).

## Gerar

Na maquina de build: Windows x64, Python 3.11 com pip, Node/npm e FFmpeg/ffprobe
conhecidos. Essas ferramentas nao precisam estar instaladas no PC que usa o pacote.

```powershell
.venv\Scripts\python.exe -B packaging/build_bundle.py
```

O build baixa CPython embeddable 3.11.9 da origem oficial e verifica SHA256;
instala as 62 distribuicoes Python fixadas em `requirements-runtime.lock`, com
hashes, sem copiar `.venv`; usa `npm ci --omit=dev --ignore-scripts` com o lock
Node do componente. Chromium e seu headless shell sao incluidos sem perfil autenticado. Pode aproveitar
somente binarios gerenciados do cache Playwright, conferidos pela revisao esperada:

```powershell
.venv\Scripts\python.exe -B packaging/build_bundle.py --browser-cache "$env:LOCALAPPDATA\ms-playwright"
```

NotebookLM usa o perfil dedicado desse Chromium para login e renovacao
`--allow-headless --verify`. O pacote nao inclui o extra opcional `rookie-cookies`,
que le cookies de navegadores externos. O ambiente de desenvolvimento preserva
as tentativas atuais de renovacao; nao foi alterado nem exige reinstalar dependencias.

`--node`, `--ffmpeg` e `--ffprobe` permitem indicar os executaveis de build;
`--output`, `--cache` e `--skip-zip` ajudam a repetir a montagem. Os binarios
copiados precisam ser autonomos; o smoke verifica Node, FFmpeg/DirectShow e
ffprobe com PATH isolado. Build requer internet/cache para dependencias, nao contas.

## Gerar o instalador

Depois de montar o pacote, use o compilador Inno Setup 7 apenas na maquina de
build. O destino nao precisa dele. Download e verificacao na
[origem oficial](https://jrsoftware.org/isdl.php); o build validado usa 7.1.0 x64,
assinado por Pyrsys B.V. O compilador pode ficar em `.bundle-cache/`, em
[modo portable](https://jrsoftware.org/ishelp/topic_technotes.htm).

```powershell
.venv\Scripts\python.exe -B packaging/build_installer.py `
  'dist-pacote\PregacaoRecorder-release-VERSAO' `
  --iscc '.bundle-cache\inno-7.1.0\compiler\ISCC.exe'
```

O montador verifica hashes e caminhos antes de compilar e inclui somente o
inventario publico. Arquivos privados extras no diretorio de build nao entram
no instalador. Saidas: `PregacaoRecorder-Instalar-release-VERSAO.exe`, checksum
`.exe.sha256`, script gerado e log local em `dist-pacote/`.

Instala por usuario em `%LOCALAPPDATA%\PregacaoRecorder`, sem elevar privilegios,
e cria um unico atalho na area de trabalho. Nao inicia servicos nem contas ao
final da instalacao. Reinstalar preserva configuracao, banco, sessoes e audios;
antes da substituicao copia os componentes anteriores e configuracao/dados para
`PregacaoRecorder-backups\DATA-HORA`, ao lado do destino. Audios nao sao duplicados.
Backups podem conter segredos e devem permanecer privados.

O instalador recusa processos ativos, trava do iniciador, juncoes e pastas
preexistentes sem manifesto. Nao encerra processos. A desinstalacao exige
ociosidade e remove componentes instalados, preservando dados criados pelo uso.
O instalador generico nao migra contas entre PCs nem restaura automaticamente.

## Conteudo e uso

- `gravador/`: fontes, painel, defaults publicos e exemplos.
- `pipeline/`: fontes minimas e prompt preservado, template sem configuracao pessoal.
- `runtime/`: Python/bibliotecas, Node, FFmpeg/ffprobe e Chromium.
- `package-manifest.json`: origem da revisao, versoes e hashes dos arquivos.
- `Iniciar Pregacao.cmd` e `Verificar Pacote.cmd`: usam somente o Python do pacote.
- `Conectar WhatsApp.cmd`: Node privado, pareamento sem enviar arquivo.
- `GUIA-INSTALACAO.md`: audio, contas, PINs e celular/broker.
- `ACEITE_WINDOWS.md`: roteiro e registro das provas reais da sprint 3.

Extraia a pasta completa para um destino gravavel. `Verificar Pacote.cmd` e
somente leitura; `Iniciar Pregacao.cmd` inicia o programa e cria os caminhos locais
iniciais, segredo local e identidade MQTT exclusiva quando ausentes. Selecionar
audio/pasta e conectar contas continua necessario. Instale no destino definitivo:
mover depois do primeiro uso pode invalidar os caminhos absolutos salvos.

Saidas em `dist-pacote/`, cache em `.bundle-cache/`; ambos ignorados pelo Git.
O ZIP, logs de build e dependencias nao sao commitados. A copia de fontes usa
allowlist: nao leva `.env`, configuracao pessoal, banco, audios, logs, cookies,
QRs, perfis ou o `node_modules` do PC original. Node e instalado a partir do lock.

## Validar

O build executa `smoke_bundle.py` com o Python privado e ambiente isolado:
imports com origem conferida; PDF e XLSX locais; Chromium offline e perfil
persistente headless sem canal explicito; versao e ajuda de login/refresh do
NotebookLM; imports Node dentro do pacote; DirectShow e MP3 sintetico/ffprobe;
diagnostico do launcher sem gravar configuracao. Sem login, conexao de conta,
captura real, upload ou envio. Credenciais ausentes geram avisos esperados.

Para repetir o smoke, a partir da raiz deste repositorio:

```powershell
& 'CAMINHO-DO-PACOTE\runtime\python\python.exe' -B packaging/smoke_bundle.py 'CAMINHO-DO-PACOTE'
```

A prova neste PC com PATH isolado nao substitui Windows limpo, driver/interface
de audio e contas reais no destino. Essas provas permanecem na sprint 3.

Fluxos da sprint 2 revisados: testar audio selecionado sem salvar; CONFIG valida
e persiste por lote; MQTT e editavel no cartao administrativo, com senha/token
vazios preservados. A CONFIG MQTT salva prevalece sobre o `.env` legado e exige
reiniciar os servicos (guia: reiniciar Windows e abrir atalho). Os 488 testes
isolados e as 11 provas do instalador passaram; resultados atuais em
[TESTES.md](../docs/TESTES.md). Configuracao pessoal e aceite no destino pendentes.

O instalador tambem tem smoke real com fixtures pequenas, sem contas, atalho ou
registro no Windows. Compila a mesma logica, instala/reinstala em pasta temporaria,
valida backup e preservacao e recusa processo ativo/lock/junction:

```powershell
.venv\Scripts\python.exe -B packaging/smoke_installer.py
```

`--iscc` permite outro caminho do compilador. `--work` exige uma pasta nova.
Builds `-smoke.exe` sao fixtures de validacao e nao devem ser entregues ao usuario.

Referencias: [task](../docs/TASK_DISTRIBUICAO_WINDOWS.md),
[Python embeddable](https://docs.python.org/3.11/using/windows.html#the-embeddable-package),
[Playwright browsers](https://playwright.dev/python/docs/browsers).

## Edicao pessoal no SSD

O usuario autorizou explicitamente incorporar todas as contas e dados atuais
no instalador privado. `build_personal_portable.py` valida um pacote publico,
copia o estado local com backup consistente do SQLite, inclui o APK e cria
instalador Inno sem registro/desinstalador. A pasta padrao e relativa ao
proprio `.exe` (`{src}\PregacaoRecorder-Pessoal`); o primeiro inicio ajusta os
caminhos absolutos quando a letra ou a pasta do SSD muda. Reinstalar preserva
os dados privados existentes. O pacote generico acima continua sem dados.

```powershell
python packaging/build_personal_portable.py dist-pacote/PregacaoRecorder-sprint2-20261020T000353363243Z --iscc .bundle-cache/inno-7.1.0/compiler/ISCC.exe --stage-root D:\PRP
python packaging/verify_personal_portable.py E:\PregacaoRecorder-Pessoal
```

A montagem usa pasta curta por causa dos caminhos do perfil do navegador no
Windows. `verify_personal_portable.py` confere o estado imediatamente apos a
instalacao; dados privados podem mudar legitimamente com o uso. O instalador
privado original permanece em `dist-pacote/`, fora do Git. A pasta pessoal
foi restaurada da Lixeira do SSD e atualizada em 20/10/2026; a pasta antiga
permanece apenas na Lixeira, fora da raiz ativa. Uma copia anterior da pasta
antiga foi arquivada em `recovery/ssd-root-archive-20261020/`, ignorada pelo
Git. Nao publicar esses artefatos. Consulte
[GUIA_SSD_PORTATIL.md](../docs/GUIA_SSD_PORTATIL.md) para uso, celular,
contas e testes no outro PC.

## Atualizar a pasta pessoal existente

Para novas versoes, use o atualizador sem estado privado. Ele leva o pacote
publico novo e o APK, aceita somente a pasta
`PregacaoRecorder-Pessoal` ja instalada, confere que ela esta fechada e faz uma
copia dos arquivos publicos antigos em `gravador/recovery/update-*` dentro
dessa pasta. Nao leva nem substitui configuracao, banco, contas, perfis,
gravacoes ou credenciais do laboratorio. O numero de serie do volume permite
ao inicio automatico encontrar o SSD mesmo se a letra mudar.

```powershell
.venv\Scripts\python.exe -B packaging/build_personal_update.py `
  'dist-pacote\PregacaoRecorder-release-VERSAO' `
  --apk 'flutter\pregacao_controle\PregacaoControle-2.7.apk' `
  --iscc '.bundle-cache\inno-7.1.0\compiler\ISCC.exe'
```

O atualizador `update-20261020T222820Z` ja foi aplicado a pasta pessoal no
SSD; o APK 2.7 tambem esta nela. Para uma versao futura, copie o `.exe` e o
`.exe.sha256` resultantes para dentro da pasta pessoal no SSD, feche as tarefas
e o programa, execute o atualizador e confira a pasta escolhida na tela do
instalador. Assim a raiz do SSD nao ganha outra pasta. Nao
execute o `build_personal_portable.py` com dados do laboratorio para atualizar
o SSD real: esse montador incorpora o estado privado da maquina de origem.

O instalador pessoal e o atualizador registram o inicio ao entrar no Windows
para o usuario atual. Na maquina instalada, estes comandos conferem, ativam ou
desativam essa opcao, sem depender da letra atual do SSD:

```powershell
$inicio = "$env:LOCALAPPDATA\PregacaoRecorder-Personal-Autostart\autostart.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $inicio -Mode Status -Layout Personal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $inicio -Mode Enable -Layout Personal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $inicio -Mode Disable -Layout Personal
```

Se o SSD nao estiver conectado ao entrar no Windows, o iniciador espera ate
60 segundos; depois registra o erro em `ultimo-erro.txt` na mesma pasta local.
Conecte o SSD e abra `Iniciar Pregacao.cmd` para essa sessao. A proxima entrada
no Windows com o SSD conectado volta a iniciar automaticamente.

## Inventario da sprint 1

- `.gitignore`
- `app/bundled_runtime.py`
- `app/estudos.py`
- `app/launcher.py`
- `docs/CODEX_CONTEXT.md`
- `docs/SPRINTS.md`
- `docs/TASK_DISTRIBUICAO_WINDOWS.md`
- `docs/TESTES.md`
- `docs/WINDOWS.md`
- `iniciar-tudo.bat`
- `packaging/README.md`
- `packaging/build_bundle.py`
- `packaging/requirements-runtime.in`
- `packaging/requirements-runtime.lock`
- `packaging/smoke_bundle.py`
- `requirements.txt`
- `scripts/pregacao.cmd`
- `tests/test_bundle_builder.py`
- `tests/test_bundled_runtime.py`
- `tests/test_nlm_login.py`
- `tests/test_vendor_pipeline.py`
- `vendor/sermon-pipeline/.gitignore`
- `vendor/sermon-pipeline/README.md`
- `vendor/sermon-pipeline/SOURCE.json`
- `vendor/sermon-pipeline/config.example.json`
- `vendor/sermon-pipeline/package-lock.json`
- `vendor/sermon-pipeline/package.json`
- `vendor/sermon-pipeline/pipeline.py`
- `vendor/sermon-pipeline/prompt.txt`
- `vendor/sermon-pipeline/whatsapp/send.js`

## Arquivos alterados na sprint 2

- `CONTEXTO_AUDITORIA_PRODUTO.md`
- `app/bundled_runtime.py`
- `app/estudos.py`
- `app/launcher.py`
- `docs/CODEX_CONTEXT.md`
- `docs/GUIA_INSTALACAO_WINDOWS.md` (novo)
- `docs/SPRINTS.md`
- `docs/TASK_DISTRIBUICAO_WINDOWS.md`
- `docs/TESTES.md`
- `docs/WINDOWS.md`
- `packaging/README.md`
- `packaging/build_bundle.py`
- `packaging/build_installer.py` (novo)
- `packaging/installer.iss` (novo)
- `packaging/requirements-runtime.in`
- `packaging/requirements-runtime.lock`
- `packaging/smoke_bundle.py`
- `packaging/smoke_installer.py` (novo)
- `tests/test_bundle_builder.py`
- `tests/test_bundled_runtime.py`
- `tests/test_installer_builder.py` (novo)
- `tests/test_launcher.py`
- `tests/test_nlm_login.py`
- `tests/test_remote_pairing_ui.py` (novo)
- `web/static/app.js`
- `web/templates/index.html`
