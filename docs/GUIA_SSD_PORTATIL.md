# Pregacao Recorder no SSD portatil

Esta pasta pessoal contem configuracao, `.env`, token do Drive, banco/historico,
gravacoes, arquivos de estudo, sessao WhatsApp e perfil NotebookLM. Use somente
`PregacaoRecorder-Pessoal` para a operacao configurada. Em 20/10/2026, a pasta
pessoal foi recuperada da Lixeira do SSD e atualizada; a pasta antiga continua
somente na Lixeira, fora da raiz ativa. O Windows mantem pastas de sistema
ocultas. A raiz contem o instalador completo para o novo PC, o APK 2.7 e
`INSTALAR-NO-OUTRO-PC.txt`. O instalador publico sem dados e o ZIP foram
preservados em `Pacote-Publico-Sem-Dados`.

## Instalar no PC sem depender do SSD

Execute `PregacaoRecorder-Completo-Instalar-local-20261021T024329576035Z.exe`
na raiz do SSD. Ele copia programa, runtimes, contas, banco, estudos e gravacoes
para `%LOCALAPPDATA%\PregacaoRecorder-Pessoal` no novo PC. Depois, abra o atalho
`Pregacao Recorder Pessoal` no desktop e teste o audio e as contas. O inicio
automatico desse PC aponta para a copia local; retirar o SSD nao remove o
programa nem seus dados locais. Consulte o
[guia da instalacao local](GUIA_INSTALACAO_LOCAL.md).

A copia no SSD permanece disponivel. As duas copias usam o mesmo ID MQTT e
nao devem ficar abertas juntas. Novas gravacoes e alteracoes feitas no PC
local nao sao sincronizadas automaticamente com o SSD.

## Usar diretamente do SSD

1. Abra `Iniciar Pregacao.cmd` dentro de `PregacaoRecorder-Pessoal`. A pasta
   instalada inclui runtimes e dados.
   Ao mudar a letra do SSD, a abertura ajusta os caminhos do banco e da
   configuracao; use sempre o `.cmd` na pasta pessoal.
2. O painel do PC aparece no navegador. Depois da abertura, execute
   `Verificar Pacote.cmd` para conferir as dependencias e caminhos locais.
3. Feche as gravacoes e tarefas antes de remover o SSD. Fechar so a aba do
   navegador nao encerra o gravador e o agente; encerre os processos pelo
   metodo habitual ou desligue o PC antes de retirar a unidade.

## Atualizar sem perder o estado do SSD

O atualizador `PregacaoRecorder-Pessoal-Atualizar-update-20261020T222820Z.exe`
ja foi aplicado no SSD. Ele confere SHA-256 e substitui somente arquivos
publicos ausentes ou diferentes; o APK atualizado fica na pasta pessoal.
Contas, credenciais, historico, banco e gravacoes foram preservados. Os backups
publicos anteriores ficam em `gravador/recovery/update-*`. Nao e necessario
executar o atualizador novamente ao conectar o SSD no outro PC.

Se a copia do SSD for a instalacao principal, execute
`Ativar Inicio Automatico.cmd` dentro da pasta pessoal no PC onde ela sera
usada. Ele localiza o SSD pelo numero de serie do volume, mesmo que a letra
mude. Se o SSD estiver ausente por mais de 60 segundos ao entrar no Windows,
abra `Iniciar Pregacao.cmd` ao conecta-lo. Se instalou a copia completa local,
o instalador ja registrou o inicio local: nao ative tambem o inicio pelo SSD.
As opcoes estao na pasta pessoal e nas
[instrucoes de empacotamento](../packaging/README.md#atualizar-a-pasta-pessoal-existente).

O programa inclui Python, Node, FFmpeg e navegador proprios e exige Windows
10/11 x64. A interface de audio ainda precisa ser reconhecida pelo Windows
do PC usado. Se o dispositivo nao existir nesse PC, escolha e teste outro em
**CONFIG > CONFIGURACOES AVANCADAS > TESTAR SINAL**. Grave alguns segundos e
ouca o arquivo antes de uma reuniao real.

## Celular

O aplicativo Android atualizado esta em `PregacaoControle-2.7.apk` na raiz do
SSD e na pasta pessoal. A tela mostra conexao com broker/PC, estado e tempo da
gravacao, envio ao Drive,
arquivo, progresso do estudo, programacao e eventos. O botao **INICIAR GRAVACAO** inicia;
**ENCERRAR GRAVACAO** pede confirmacao antes de finalizar. As respostas e
mudancas de estado chegam pelo MQTT. A programacao permite consultar, criar,
editar e excluir diretamente na primeira pagina, sem pedir PIN no celular.
Dois celulares podem operar ao mesmo tempo; se ambos editarem a mesma pregacao,
o segundo recebe aviso de versao desatualizada para conferir a lista.

O pacote conserva o ID do equipamento e as credenciais MQTT do PC. Se o
celular ja controla este mesmo equipamento, mantenha a configuracao do app:
ele continuara usando os mesmos topics. Se instalar o APK em outro celular,
abra **CONFIG > CONFIGURACOES AVANCADAS > CONTROLE REMOTO** no painel do PC e
copie ID, broker, porta/TLS e token do operador para o app. A instalacao no
Windows nao instala automaticamente o APK nem transfere o armazenamento
privado do telefone.

O laboratorio usa um ID MQTT diferente da instalacao pessoal; nao configure
o celular da operacao real com o ID do laboratorio. O PC precisa de internet e acesso ao
broker para o celular funcionar fora da rede local.

## Contas e arquivos

O historico e os arquivos anteriores estao na pasta instalada. Novas
gravacoes da copia portatil vao para `gravador\recordings` no SSD; na copia
completa local, vao para a pasta instalada no PC. O instalador publico em
`Pacote-Publico-Sem-Dados` cria uma instalacao vazia. Nao reinstale por cima de
uma pasta com tarefas em andamento; a reinstalacao preserva banco,
gravacoes, configuracoes e sessoes que mudaram apos a primeira instalacao.

O token do Drive, a sessao WhatsApp e o estado do NotebookLM foram copiados
na instalacao pessoal original.
Teste cada integracao no outro PC: os provedores podem expirar ou invalidar
sessoes; perfis de navegador podem depender da conta Windows original. Se
isso ocorrer, renove o login pelo painel ou `Conectar WhatsApp.cmd`. O pacote
nao cria driver de audio, conexao de internet nem permissao nova no broker.

O usuario informou que conseguiu entrar no NotebookLM no outro PC. O
atualizador preserva esse login no SSD; a execucao real de um estudo continua
pendente de teste la. Nao use o instalador privado antigo para atualizar os
arquivos do programa apos esse login, pois ele carrega o estado da epoca em
que foi gerado.

## Conferencia no outro PC

1. Instale a copia completa local e confirme que CONFIG mostra a mesma
   identidade e contas da copia do SSD.
2. Teste sinal, inicie e encerre uma gravacao curta no PC e no celular;
   confira timer, estado, evento, arquivo e audio reproduzido.
3. Confirme o envio ao Drive e, se usados, NotebookLM/PDF e WhatsApp com
   destinatario de teste.
4. Feche a copia do SSD, remova a unidade e abra a copia local. Confira
   historico, gravacoes, pasta de destino e inicio apos nova entrada no Windows.
   Se usar a copia portatil em outro PC, repita a abertura e o teste de sinal.
