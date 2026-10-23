# Entrega Windows e Android

A entrega pessoal é gerada como dois arquivos independentes: o instalador Windows
com MQTT, Google Drive, NotebookLM e WhatsApp, e o APK com a conexão MQTT do
operador já preenchida. Ambos contêm credenciais e ficam fora do GitHub. Para
recriá-los com as conexões atuais, use
`build_connected_release.py` conforme a seção **Instalador pessoal** abaixo.

## Edição pública sem credenciais

Use `build_release.py` para gerar os dois artefatos independentes:

```powershell
.venv\Scripts\python.exe -B packaging/build_release.py
```

Saída em `dist-pacote/`:

- `Gerador de Estudo.exe` e `Gerador de Estudo.exe.sha256`;
- `Controle Android.apk` e `Controle Android.apk.sha256`.

Requisitos na máquina de build: Windows x64, Python 3.11, Flutter com Android
SDK, Node/npm, FFmpeg/ffprobe, Inno Setup 7 e acesso à internet ou cache das
dependências. A máquina de destino recebe Python, Node, FFmpeg e Chromium dentro
do instalador; não precisa dessas ferramentas de desenvolvimento. Use `--flutter`,
`--iscc`, `--browser-cache`, `--cache` e `--output` para apontar outros caminhos.
O cache padrão fica em `.bundle-cache/` e a montagem temporária em `.w/`,
ambos dentro do projeto. Flutter, Gradle, Pub, npm e os testes de pacote usam
essas pastas durante o build. Nenhuma pasta de montagem é criada na raiz de D:.
O APK usa `.signing/debug.keystore` dentro do projeto para manter a assinatura
das versões já instaladas; a chave é ignorada pelo Git e não entra no pacote.

Depois de conferir os dois arquivos finais, `limpar_gerados.ps1` mostra os
instaladores antigos, caches e o build intermediário do Flutter que podem ser
removidos. A prévia não apaga nada; para executar a limpeza:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\limpar_gerados.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\limpar_gerados.ps1 -Execute
```

O script confere os hashes da entrega, limita a remoção aos artefatos gerados,
recusa links/junções e preserva `recovery/`, `data/`, `recordings/`, `.venv/` e
o compilador Inno usado pelo próximo build.

O build inclui fontes por lista fechada, instala dependências Python fixadas
por hash, obtém o Chromium da revisão do Playwright, executa um smoke offline do
pacote e compila o Inno Setup. A pasta intermediária é temporária; o APK nunca
entra no instalador. O manifesto validado impede incluir `.env`, banco, áudios,
perfis de navegador, credenciais, tokens e arquivos que não pertençam ao código
ou runtime. O instalador contém um desinstalador e aceita escolher a pasta.

Na instalação, o início automático é registrado apenas para o usuário Windows
atual. A bandeja inicia os serviços sem abrir o navegador; o atalho da área de
trabalho usa `app.launcher --abrir-painel`, que abre somente o endereço local.
Ao desinstalar, o programa fecha os processos verificados dessa instalação se
estiver ocioso. Instalar novamente no mesmo local move os dados locais para
`<pasta>-dados-anteriores/<data>` antes de instalar uma cópia limpa. Não há
cópia dos runtimes antigos nem duplicação das gravações.

Para validar o instalador com arquivos sintéticos, sem abrir contas nem criar
atalhos ou registro no Windows:

```powershell
.venv\Scripts\python.exe -B packaging/smoke_installer.py
```

## Instalador pessoal

Para gerar o instalador e o APK pessoal no mesmo diretório, use:

```powershell
.venv\Scripts\python.exe -B packaging/build_connected_release.py --output "dist-pacote-pessoal\Gerador de Estudo.exe"
```

O APK `Controle Android.apk` aparece ao lado do instalador e já recebe host,
porta, TLS, ID do equipamento, usuário `operador` e o token do operador. O
instalador inclui a credencial MQTT do PC, o cliente OAuth e o token renovável
do Google Drive. Ele também copia a sessão atual do NotebookLM e, quando
existir, a sessão vinculada do WhatsApp e os destinatários configurados.
Depois do build, copie os dois arquivos e seus `.sha256` para a mídia de entrega;
esta entrega foi copiada para a raiz de `E:\` e verificada por SHA-256.

Para o NotebookLM conseguir recriar a sessão mesmo depois de todos os cookies
expirarem, faça uma autorização durável no navegador antes de gerar a entrega:

```powershell
.venv\Scripts\python.exe -B packaging/ativar_login_notebooklm.py --account voce@gmail.com
```

O script grava o token durável em `data/notebooklm/profiles/default/master_token.json`
e verifica a sessão. Sem esse token, o build ainda leva a sessão atual existente;
se ela expirar, **RENOVAR LOGIN** no painel ou **RENOVAR LOGIN NO PC** no APK
abre o navegador do PC. O `LEIA-ME.txt` identifica qual modo foi incluído.
O marcador portátil ajusta os caminhos de estudos e gravações no primeiro
início. Banco, gravações e backups não entram na entrega. Atualizar o APK no
mesmo celular preserva as alterações de conexão feitas no aparelho.
