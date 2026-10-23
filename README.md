# Gerador de Estudo

Gravador de pregações para Windows, com painel local, envio ao Google Drive,
geração de estudos e controle Android por MQTT/TLS.

## Instalar em outro PC

A entrega pessoal está em `E:\Gerador de Estudo\`, com dois arquivos independentes:

- `Gerador de Estudo.exe`: instalador Windows x64.
- `Controle Android.apk`: aplicativo para cada celular Android.

Esse instalador pessoal leva o programa, os runtimes, a configuração do broker
MQTT e a autorização OAuth já concedida à conta Google Drive. **Ele contém
credenciais: guarde o `.exe` em local privado e não o publique no GitHub.** A
instalação começa sem histórico, gravações, banco de dados, backups, sessões de
navegador, NotebookLM ou WhatsApp. Os arquivos já existentes no Drive permanecem
na nuvem; o programa não os baixa automaticamente. A gravação local funciona
mesmo sem a conta Google ativa; o envio aguarda autorização e conexão.

Execute o `.exe`, escolha a pasta desejada e siga o assistente. O Windows cria
**Gerador de Estudo** na área de trabalho e no menu Iniciar. Esse atalho abre
somente o painel no navegador; o serviço inicia com o Windows e aparece na
bandeja do sistema. Ícone dourado indica painel ativo, vermelho indica que ele
não responde. O menu da bandeja permite abrir o painel ou tentar iniciar o
serviço. Na primeira utilização, escolha a interface de áudio e a pasta de
gravação no novo PC. Confira a conexão com o Drive e o broker no painel.
NotebookLM e WhatsApp exigem login próprio, caso sejam usados.

Para desinstalar, use **Desinstalar Gerador de Estudo** no menu Iniciar ou
**Configurações > Aplicativos** do Windows. O desinstalador encerra os serviços
quando não há gravação, upload ou estudo pendente. Ele preserva os dados criados
após a instalação. Se instalar de novo na mesma pasta, esses dados são movidos
para uma pasta irmã `Gerador de Estudo-dados-anteriores`; a instalação nova
começa vazia, sem duplicar os áudios. Pode escolher outra pasta na instalação.

O instalador pessoal antigo `PregacaoRecorder-Completo-Instalar-...` não
registrava desinstalador. O instalador novo desativa o início automático dessa
versão antiga. Se ela estava aberta no PC, reinicie o Windows após instalar para
liberar a porta do painel. Guarde ou remova a pasta antiga manualmente após
conferir que não há gravações únicas nela.

O APK fica **fora** do instalador Windows. Instale `Controle Android.apk` em cada
celular. No telefone, mantenha ou configure o mesmo ID MQTT e as credenciais de
operador; o instalador preserva a conexão do lado do PC. Para mostrar
eventos ocorridos enquanto o celular estava fechado, o PC inclui os últimos
eventos no estado MQTT retido. O tópico adicional `pregacao/<id>/history` pode
ser autorizado no broker para um histórico maior.

O guia desta entrega está em
[docs/GUIA_INSTALACAO_CONECTADA.md](docs/GUIA_INSTALACAO_CONECTADA.md).
O [guia genérico](docs/GUIA_INSTALACAO_WINDOWS.md) descreve a edição pública,
que começa sem credenciais.

## Gerar a entrega

Em Windows x64, com Python 3.11, Flutter/Android SDK, Node, FFmpeg e Inno Setup:

```powershell
.venv\Scripts\python.exe -B packaging/build_release.py
```

Esse comando gera a edição pública, sem credenciais, em `dist-pacote/`. Para
recriar o instalador pessoal com as conexões atuais, use
`packaging/build_connected_release.py` conforme
[packaging/README.md](packaging/README.md). Os arquivos antigos e backups desta
máquina ficam em `.OLD/`, ignorada pelo Git. Veja
[docs/ARQUIVOS_ANTIGOS.md](docs/ARQUIVOS_ANTIGOS.md). O painel fica em `app/` e
`web/`; o aplicativo Android atual fica em `flutter/pregacao_controle/`.

## Uso

O fluxo é mesa/microfone → segmentos WAV → MP3 local. Upload ao Drive e estudo
entram em filas independentes; o estudo pode gerar PDF e enviar pelo WhatsApp.
O celular envia comandos e mostra estado, programação, progresso e os últimos
eventos persistidos pelo PC. A gravação local funciona sem internet.

Em **CONFIG**, configure as contas e recursos opcionais. Durante uma gravação,
**FINALIZAR GRAVAÇÃO** salva e processa o áudio; **DESCARTAR GRAVAÇÃO** apaga a
captura mediante confirmação. Consulte [GUIA-USUARIO.md](GUIA-USUARIO.md) para
as funções do painel.

Os testes de captura real, contas e dois celulares devem ser feitos no PC de
destino, com a interface de áudio e o broker que serão usados na operação.
