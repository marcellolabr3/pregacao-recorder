# Validacao - Windows

## Suite Python

Revalidacao independente em 19/10/2026: **309 testes passaram em 16,41 s** em copia
temporaria contendo somente fontes, testes e configuracao padrao. Credenciais,
gravacoes e banco reais nao foram copiados. Testes exclusivos da plataforma
retirada foram removidos; cobertura ativa foi adaptada e ampliada para Windows.
O total inclui 25 testes do novo iniciador unico (`tests/test_launcher.py`).
Inclui tambem 16 casos do login monitorado (`tests/test_nlm_login.py`).

Para repetir com o venv preparado:

```powershell
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short
node --check web/static/app.js
```

`tests/conftest.py` define home temporario antes dos imports e usa bancos isolados.
Para a validacao final desta tarefa foi utilizada tambem uma copia das fontes fora
do projeto. Nao executar scripts de teste ativo contra o servidor real por engano.

## Cobertura da retirada

- Rotas de configuracao de interfaces inexistentes (GET/POST retornam 404).
- Comandos antigos de gestao de rede recusados; gravacao/Drive/storage preservados.
- Discos/pastas: consultas sem criar diretorios, recusa de caminho relativo,
  arquivo, volume ausente e falta de permissao; pasta criada apenas ao escolher.
- Captura DirectShow mesmo se houver ferramenta legada no PATH.
- Home padrao na pasta do projeto; override e destino configurado preservados.
- Configuracoes antigas ignoradas sem reescrever o arquivo local.
- Formularios HTML independentes e campos associados ao formulario correto.
- Nova captura recusada quando destino esta indisponivel.

## Navegador (evidencias da sessao anterior)

Chromium/Playwright headless, APIs simuladas e nenhuma acao no servidor real:
boot, CONFIG, area avancada, abrir/fechar cadastro e salvar avancadas passaram.
Zero erros JavaScript e zero chamadas de administracao de rede.
A sintaxe JavaScript passou em `node --check`. Navegador real tambem abriu sem
erros JS, com formulario presente e sem controles de rede do equipamento.
O servidor real foi reiniciado apos conferir ausencia de captura, uploads, estudos
e login em execucao. APIs de integracoes/pregacoes/modelo retornaram 200; painel
serve o cache `nlm2`. Os dois estudos em espera foram preservados.

## Renovacao de login NotebookLM

- Sessao nova do navegador dedicado, prazo de 10 minutos, monitoramento assincrono
  e uma unica janela; nenhuma alteracao no pacote instalado ou pipeline externo.
- Codigo zero no login sem auth check passivo valido nao libera os estudos.
- Cancelamento/erro/rede preservam os jobs; confirmacao retoma os mesmos registros.
- Checks/refreshs nao competem com login; regressao das corridas com pre-flight e
  retomada, snapshot de status, permissoes admin e recuperacao de erro cobertas.
- UI Playwright totalmente simulada: clique duplo vira um pedido, botoes bloqueados,
  fases/erro/confirmacao e estudos retomados aparecem pelo polling sem recarregar.
- Diagnostico real somente leitura: cookies presentes, token_fetch=false. Nenhum
  login/refresh foi disparado, nenhum estudo foi retomado nem houve envio real.
- Correcao ativa no servidor real; a nova entrada na conta depende do usuario no PC.

## Iniciador unico

- Testes isolados: reuso/identidade de PID, porta ocupada, FFmpeg/dependencias ausentes,
  timeout, saida precoce, ambiente do venv, HOME e URL configurados, logs separados,
  somente agente sem API e falha MQTT sem encerrar gravador.
- `--verificar` testado sem criar banco, logs ou processos de servico.
- Smoke real Windows com modulos falsos em pasta temporaria: processos ocultos,
  caminhos com espacos e `&`, dois iniciadores concorrentes, uma unica instancia,
  API pronta e agente reutilizado. Todos os processos falsos foram encerrados.
- BAT executado em copia preparada com `--verificar` e retorno zero.
- Diagnostico da instalacao real encontrou Python, bibliotecas do gravador/Drive/MQTT,
  FFmpeg/ffprobe, Node/rclone, destino, credenciais/token e caminhos do pipeline.
  Nao confirmou logins nem iniciou gravacao, filas ou conexao MQTT.

## Limites

Nao houve gravacao real, upload, envio WhatsApp ou comandos MQTT nesta validacao.
Nao foram executados Flutter test/build nem build da fonte Kotlin legada.
O conteudo de rede removido da fonte nao atualiza APK ja instalado.
Provas de captura na mesa, dois celulares, queda de conexao e reinicio controlado
continuam no `CHECKLIST.md`. Dependencias do pipeline externo nao foram modificadas.

## Revisao independente para consolidacao no GitHub

Codigo base `5c9549f`: suite repetida com Python 3.11.9/pytest 9.1.1 em copia
contendo apenas `app/`, `tests/`, `web/`, `config/default.json` e `pytest.ini`.
Nenhuma configuracao real, credencial, banco ou gravacao foi copiada. Foram
validados por parse 56 arquivos Python, sintaxe JS e XML/recursos Android.
Credenciais locais e padroes de tokens/chaves foram comparados com os 69 arquivos
incluidos/alterados no commit sem exibir valores; nenhum achado nessa varredura.

Limitacoes encontradas por inspecao e simulacoes: corrida login/pipeline (G01),
identidade entre instalacoes (G02) e texto legado de fallback (G03). Elas nao foram
corrigidas nesta consolidacao; ver `../CONTEXTO_AUDITORIA_PRODUTO.md`.
Os 309 testes verdes nao provam ausencia dessas falhas. Playwright/smoke Windows
acima sao evidencias anteriores e nao foram repetidos nesta revisao. Nenhuma
acao real de captura, login, upload, envio ou reinicio de servicos foi executada.
