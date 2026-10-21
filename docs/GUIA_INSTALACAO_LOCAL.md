# Instalacao completa no PC Windows

Este instalador traz o programa, os runtimes, as contas configuradas, o banco,
o historico, os estudos e as gravacoes da pasta pessoal atual do SSD. Ele
instala uma copia em %LOCALAPPDATA%\PregacaoRecorder-Pessoal para o usuario
Windows atual. Depois da instalacao, a copia local funciona sem o SSD.

O instalador completo gerado antes da interface 2.8 ainda inclui o painel e
APK anteriores. O pacote e o atualizador 2.8 ja foram compilados, mas um novo
instalador completo depende da pasta pessoal atual do SSD. Nao use um backup
antigo como origem se deseja levar todas as contas e gravacoes recentes.

1. Feche o programa no SSD antes de instalar e antes de abrir a copia local.
   As duas copias usam a mesma identidade MQTT e nao devem rodar juntas.
2. Execute PregacaoRecorder-Completo-Instalar-*.exe na raiz do SSD. O instalador
   recusa substituir uma pasta local que ja contenha dados.
3. Abra o atalho "Pregacao Recorder Pessoal" na area de trabalho ou
   Iniciar Pregacao.cmd na pasta local. O primeiro inicio ajusta para o PC
   os caminhos das gravacoes, do pipeline, do NotebookLM e do historico.
4. Execute Verificar Pacote.cmd na pasta local. Teste o dispositivo de audio,
   abra CONFIG e confira as integracoes antes de uma reuniao real.
5. O inicio automatico fica registrado para essa copia local e nao depende
   da letra ou da presenca do SSD. O SSD pode ser removido apos fechar a copia
   portatil e concluir a instalacao.

O aplicativo Android 2.7.0+13 esta em PregacaoControle-2.7.apk na raiz do SSD,
na pasta pessoal do SSD e na copia local instalada. O instalador Windows nao
instala o APK nos celulares: abra o arquivo em cada um para instalar ou
atualizar o aplicativo. A assinatura e a mesma da versao anterior; atualize
sem desinstalar o aplicativo antigo para preservar sua configuracao. O APK nao
pede PIN, mas conserva a configuracao e o token MQTT. Como a identidade do
gravador foi preservada, os celulares devem apontar para o PC que estiver
ligado. Nao execute a copia local e a copia do SSD ao mesmo tempo.

Os arquivos de autenticacao seguem na instalacao, mas provedores podem pedir
novo login ao mudar de PC ou de usuario Windows. Se isso ocorrer, renove a
conta no painel ou use Conectar WhatsApp.cmd. O instalador nunca envia
mensagens WhatsApp nem inicia um estudo.

Os backups de atualizacoes anteriores permanecem no SSD. A copia local leva
os dados ativos, inclusive gravacoes, banco, estudos e perfis. Novas alteracoes
feitas na copia local nao sao sincronizadas automaticamente com o SSD.
