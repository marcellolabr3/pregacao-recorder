# Entrega Windows e Android

A entrega pessoal atual está em `E:\Gerador de Estudo\`: o instalador Windows
preserva a configuração MQTT e a autorização OAuth do Google Drive, enquanto o
APK permanece separado. Esse instalador contém credenciais e deve ficar fora do
GitHub. Para recriá-lo com as conexões atuais, use
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

Os montadores antigos que copiavam histórico, gravações e sessões foram movidos
para `.OLD/packaging/`; eles não fazem parte do build atual.

## Instalador pessoal

Para a entrega pessoal que mantém apenas as conexões do PC atual, use:

```powershell
.venv\Scripts\python.exe -B packaging/build_connected_release.py --output "E:\Gerador de Estudo\Gerador de Estudo.exe"
```

Esse instalador inclui as preferências e credenciais MQTT, o cliente OAuth e o
token renovável do Google Drive. O marcador portátil ajusta os caminhos de
estudos e gravações no primeiro início. Ele não inclui banco, gravações,
backups, perfis de navegador ou sessões de WhatsApp/NotebookLM. O APK continua
separado; ao atualizar no mesmo celular, a configuração protegida é mantida.
A cópia pessoal deve permanecer privada porque contém credenciais.
