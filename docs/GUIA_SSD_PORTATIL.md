# Pregacao Recorder no SSD portatil

Esta pasta pessoal contem configuracao, `.env`, token do Drive, banco/historico,
gravacoes, arquivos de estudo, sessao WhatsApp e perfil NotebookLM. Use somente
`PregacaoRecorder-Pessoal` no SSD. O SSD esta no outro PC; a presenca e o estado
atual das pastas antigas ainda precisam ser conferidos la. O usuario autorizou
eliminar as pastas antigas depois de identificar a pasta pessoal correta.
O Windows pode manter pastas de sistema ocultas.

## Instalar e usar

1. Abra `Iniciar Pregacao.cmd` dentro de `PregacaoRecorder-Pessoal`. A pasta
   instalada inclui runtimes e dados. Se ela estiver ausente, use o instalador
   privado original; o atualizador novo exige a pasta pessoal ja existente.
   Ao mudar a letra do SSD, a abertura ajusta os caminhos do banco e da
   configuracao; use sempre o `.cmd` na pasta pessoal.
2. O painel do PC aparece no navegador. Depois da abertura, execute
   `Verificar Pacote.cmd` para conferir as dependencias e caminhos locais.
3. Feche as gravacoes e tarefas antes de remover o SSD. Fechar so a aba do
   navegador nao encerra o gravador e o agente; encerre os processos pelo
   metodo habitual ou desligue o PC antes de retirar a unidade.

## Atualizar sem perder o estado do SSD

Coloque o novo `PregacaoRecorder-Pessoal-Atualizar-*.exe` e seu `.exe.sha256`
dentro de `PregacaoRecorder-Pessoal`, feche tarefas e processos do programa e
execute o atualizador. Confirme que a pasta selecionada e a pasta pessoal do
SSD; ele recusa pasta vazia/outra instalacao e programa em execucao. Ele copia
somente os arquivos publicos novos e o APK atualizado, preservando contas,
credenciais, historico, banco e gravacoes. O backup dos arquivos publicos
anteriores fica em `gravador/recovery/update-*` dentro da pasta pessoal.

O instalador registra a abertura automatica ao entrar no Windows para o
usuario atual, sem abrir o navegador. Ele localiza o SSD pelo numero de serie
do volume, mesmo que a letra mude. Deixe o SSD conectado ao entrar no Windows.
Se ele estiver ausente por mais de 60 segundos, conecte-o e abra
`Iniciar Pregacao.cmd` nessa sessao. As opcoes para conferir, ativar e desativar
estao em [instrucoes de empacotamento](../packaging/README.md#atualizar-a-pasta-pessoal-existente).

O programa inclui Python, Node, FFmpeg e navegador proprios e exige Windows
10/11 x64. A interface de audio ainda precisa ser reconhecida pelo Windows
do PC usado. Se o dispositivo nao existir nesse PC, escolha e teste outro em
**CONFIG > CONFIGURACOES AVANCADAS > TESTAR SINAL**. Grave alguns segundos e
ouca o arquivo antes de uma reuniao real.

## Celular

O aplicativo Android atualizado sera instalado a partir de
`PregacaoControle-2.7.apk` na pasta pessoal. A tela
mostra conexao com broker/PC, estado e tempo da gravacao, envio ao Drive,
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
gravacoes tambem vao para `gravador\recordings` no SSD. O instalador privado
esta na raiz do SSD e tambem no PC de desenvolvimento. Nao reinstale
por cima de uma pasta com tarefas em andamento; a reinstalacao preserva banco,
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

1. Abra pelo SSD e confirme que CONFIG mostra a mesma identidade e contas.
2. Teste sinal, inicie e encerre uma gravacao curta no PC e no celular;
   confira timer, estado, evento, arquivo e audio reproduzido.
3. Confirme o envio ao Drive e, se usados, NotebookLM/PDF e WhatsApp com
   destinatario de teste.
4. Mova o SSD para outro PC com Windows x64 e repita a abertura e o teste de
   sinal. Confira que os arquivos continuam no SSD.
