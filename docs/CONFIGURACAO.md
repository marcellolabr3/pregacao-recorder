# Configuracao

A configuracao combina `config/default.json`, `config/config.json` local e variaveis
do ambiente. O `.env` e carregado sem sobrescrever variaveis ja existentes.

- CONFIG: nome, conexao Google e estudo/WhatsApp.
- CONFIGURACOES AVANCADAS: audio, pasta, retencao, OAuth e diagnosticos.
- `PREGACAO_HOME`: opcional; padrao e a pasta do projeto.
- PIN normal controla acesso; PIN admin protege alteracoes tecnicas.
- Valores vazios dos PINs mantem o comportamento de acesso livre atual.
- `network.check_host/check_port/retry_seconds`: conectividade e fila de upload.
- Chaves antigas de configuracao de interfaces sao ignoradas em memoria.

As credenciais reais, tokens e caminhos configurados nao foram reescritos pela
retirada da plataforma antiga. Opcoes de retencao/exclusao devem considerar jobs
pendentes: as limitacoes constam na auditoria (D09/D10).

## Renovar a sessao do NotebookLM

Para a copia pessoal em outro PC, cadastre uma vez o token duravel com
`.venv\Scripts\python.exe -B packaging/ativar_login_notebooklm.py`. O script
usa o email da sessao NotebookLM existente ou solicita outro email, abre o
Google uma vez e guarda o token em `data/notebooklm` dentro do projeto. O
instalador pessoal inclui esse token quando presente e a sessão existente; no novo PC
o aplicativo cria e renova os cookies sozinho. O celular mostra o estado e
permite **DIAGNOSTICAR SESSAO** e **RENOVAR LOGIN NO PC** sem transmitir o token pelo MQTT.
Se o token duravel nao estiver disponivel, a entrega pessoal inclui a sessao
atual do NotebookLM e o botao de login continua disponivel quando ela expirar.
Se o Google revogar o token, sera necessario um novo cadastro.

Em CONFIG > ESTUDO AUTOMATICO, clicar em RENOVAR LOGIN uma vez. No PC do gravador,
entrar novamente na conta Google com acesso ao NotebookLM e concluir as etapas
pedidas pelo Google. A janela pode levar ate 10 minutos aguardando a entrada.
O navegador fecha quando o CLI termina; o painel mostra depois a verificacao real.

A renovacao abre uma sessao nova no navegador dedicado ao NotebookLM (`--fresh`),
sem limpar o navegador pessoal ou apagar o storage salvo antecipadamente. Isso
evita capturar a sessao antiga e fechar a janela antes da nova entrada.
O comportamento das opcoes esta na [referencia do CLI](https://github.com/teng-lin/notebooklm-py/blob/main/docs/cli-reference.md#authentication-login).

Durante o login, os botoes ficam bloqueados e o card atualiza sozinho. Apenas
apos `auth check --test --passive` confirmar a sessao, as esperas voltam para a
fila existente. Salvar cookies ou encerrar o login com codigo zero nao basta.
Cancelamento/falha mantem os estudos em espera e mostram uma orientacao no card.
Um diagnostico posterior bem sucedido tambem remove o aviso de falha anterior.
Detalhes tecnicos permanecem no `logs/login_nlm.log` do pipeline; nao compartilhar
logs ou arquivos de autenticacao sem verificar dados sensiveis.
