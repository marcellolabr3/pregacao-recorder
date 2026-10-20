# Pregacao Recorder no SSD portatil

Esta pasta pessoal contem o estado copiado do PC de origem: configuracao,
`.env`, token do Drive, banco/historico, gravacoes, arquivos de estudo, sessao
WhatsApp e perfil NotebookLM. Na raiz visivel do SSD permanece somente
`PregacaoRecorder-Pessoal`; o Windows mantem pastas de sistema ocultas.
Use a pasta somente no seu SSD pessoal. O instalador privado foi guardado
fora do SSD e nao e publicado no GitHub.

## Instalar e usar

1. Abra `Iniciar Pregacao.cmd` dentro de `PregacaoRecorder-Pessoal`. A pasta
   ja esta instalada e inclui os runtimes, dados e APK necessarios. Ao mudar
   a letra do SSD ou a pasta, a abertura ajusta os caminhos do banco e da
   configuracao; use sempre o mesmo arquivo `.cmd` no novo local.
2. O painel do PC aparece no navegador. Depois da abertura, execute
   `Verificar Pacote.cmd` para conferir as dependencias e caminhos locais.
3. Feche as gravacoes e tarefas antes de remover o SSD. Fechar so a aba do
   navegador nao encerra o gravador e o agente; encerre os processos pelo
   metodo habitual ou desligue o PC antes de retirar a unidade.

O programa inclui Python, Node, FFmpeg e navegador proprios e exige Windows
10/11 x64. A interface de audio ainda precisa ser reconhecida pelo Windows
do PC usado. Se o dispositivo nao existir nesse PC, escolha e teste outro em
**CONFIG > CONFIGURACOES AVANCADAS > TESTAR SINAL**. Grave alguns segundos e
ouca o arquivo antes de uma reuniao real.

## Celular

O aplicativo Android esta no SSD como `PregacaoControle-2.6.apk`. A tela
mostra conexao com broker/PC, estado e tempo da gravacao, envio ao Drive,
arquivo, progresso do estudo e eventos. O botao **INICIAR GRAVACAO** inicia;
**ENCERRAR GRAVACAO** pede confirmacao antes de finalizar. As respostas e
mudancas de estado chegam pelo MQTT.

O pacote conserva o ID do equipamento e as credenciais MQTT do PC. Se o
celular ja controla este mesmo equipamento, mantenha a configuracao do app:
ele continuara usando os mesmos topics. Se instalar o APK em outro celular,
abra **CONFIG > CONFIGURACOES AVANCADAS > CONTROLE REMOTO** no painel do PC e
copie ID, broker, porta/TLS e token do operador para o app. A instalacao no
Windows nao instala automaticamente o APK nem transfere o armazenamento
privado do telefone.

Use somente uma copia do gravador com esse ID por vez. Se a copia do PC de
origem e a do SSD ficarem ligadas juntas, o broker pode derrubar uma conexao
ou o celular controlar o PC errado. O PC precisa de internet e acesso ao
broker para o celular funcionar fora da rede local.

## Contas e arquivos

O historico e os arquivos anteriores estao na pasta instalada. Novas
gravacoes tambem vao para `gravador\recordings` no SSD. O instalador privado
permanece no PC de desenvolvimento caso seja preciso reinstalar. Nao reinstale
por cima de uma pasta com tarefas em andamento; a reinstalacao preserva banco,
gravacoes, configuracoes e sessoes que mudaram apos a primeira instalacao.

O token do Drive, a sessao WhatsApp e o estado do NotebookLM foram copiados.
Teste cada integracao no outro PC: os provedores podem expirar ou invalidar
sessoes; perfis de navegador podem depender da conta Windows original. Se
isso ocorrer, renove o login pelo painel ou `Conectar WhatsApp.cmd`. O pacote
nao cria driver de audio, conexao de internet nem permissao nova no broker.

**Estado atual:** o token do Drive passou no teste local, mas a sessao do
NotebookLM ja estava expirada no PC de origem. Use **CONFIG > RENOVAR LOGIN**
para entrar nessa conta antes de iniciar um estudo novo. Se o login for feito
apos a criacao deste instalador, a pasta instalada guardara a sessao renovada;
para que outro instalador carregue a sessao nova, ele precisa ser refeito.

## Conferencia no outro PC

1. Abra pelo SSD e confirme que CONFIG mostra a mesma identidade e contas.
2. Teste sinal, inicie e encerre uma gravacao curta no PC e no celular;
   confira timer, estado, evento, arquivo e audio reproduzido.
3. Confirme o envio ao Drive e, se usados, NotebookLM/PDF e WhatsApp com
   destinatario de teste.
4. Mova o SSD para outro PC com Windows x64 e repita a abertura e o teste de
   sinal. Confira que os arquivos continuam no SSD.
