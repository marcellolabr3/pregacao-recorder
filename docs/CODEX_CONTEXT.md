# Pregacao Recorder - contexto operacional

## Inicio

- Projeto: `D:\Dev\pregacao-recorder`; ler este arquivo e `git status --short`.
- Produto Windows: Flask/waitress, SQLite, FFmpeg/DirectShow, web e Flutter/MQTT.
- Unica entrada: `iniciar-tudo.bat`; inicia os processos e abre o painel quando pronto.
- Painel padrao `http://127.0.0.1:8080`; diagnostico sem iniciar: `iniciar-tudo.bat --verificar`.
- `.venv\Scripts\python.exe`; dependencias em `requirements.txt`.
- Dados locais: `.env`, `config/config.json`, tokens OAuth, `data/`, `recordings/`.
- Nunca imprimir/commitar credenciais. `docs/CODEX_CONTEXT.local.md` e local/ignorado e contem notas legadas
  sensiveis; nao define o escopo atual. `CONTEXTO.md` agora aponta para este arquivo.

## Regras

- Preservar banco, gravacoes, credenciais e jobs; testar com home/banco isolados.
- Gravacao independe da internet/MQTT. Celular controla, PC processa.
- Nao alterar o pipeline externo sem analisar impacto.
- Pipeline atual em `C:\Users\Aska\Documents\Default Project\sermon-pipeline`.
- Historico de auditoria: `CONTEXTO_AUDITORIA_PRODUTO.md` (IDs A-F).

## Ultimo estado validado (19/10/2026)

- Retirada Raspberry/Linux concluida; escopo e inventario em `docs/REMOCAO_RASPBERRY.md`.
- Inicializacao consolidada: `iniciar-tudo.bat` chama `app/launcher.py` com o Python
  explicito da `.venv`; verifica dependencias/FFmpeg/porta, espera a API e abre navegador.
- Gravador/agente seguem separados, sem consoles extras; falha MQTT nao encerra gravador.
- Trava de inicializacao serializa cliques; identidade por PID/modulo/Python ainda tem limite entre copias (G02).
- Retirados 2 BATs separados e 8 BATs antigos de SSD; preservados `gradlew.bat`,
  `scripts/pregacao.cmd` e migrador manual `_instalador/ajustar_caminhos.py` (nao executar automaticamente).
- Opcoes: `--verificar`, `--sem-navegador`, `--somente-gravador`, `--somente-agente`.
- Logs: `inicializacao.log`/`inicio-gravador.log`/`inicio-agente.log` e logs originais dos servicos.
- Discos Windows enumerados sem criar pastas; destino ausente impede captura.
- Home padrao e a pasta do projeto; overrides e dados existentes preservados.
- Formularios web separados; painel real sem erros JS nem controles de rede antigos.
- Renovar login NotebookLM agora abre sessao nova no navegador dedicado (`--fresh`,
  timeout 600s), acompanha um unico processo e confirma com auth check passivo.
- Status de login acompanha abertura/entrada/verificacao/erro; card atualiza sozinho.
  Somente sessao confirmada retoma jobs; checks/refreshs nao disputam com o login.
- 309 testes Python verdes em copia isolada, incluindo 25 do iniciador e 16 de login;
  sintaxe Python/JS e Playwright com APIs simuladas OK.
- Smoke Windows com modulos falsos: processos ocultos, caminhos com espacos/&, cliques
  concorrentes, API pronta e reuso de PIDs OK; BAT executado com `--verificar` em copia.
- Diagnostico somente leitura da instalacao real: requisitos locais encontrados, sem
  iniciar servicos/filas/captura/envios. Esse diagnostico nao confirma as sessoes das integracoes.
- Operacao e inventario desta melhoria: `docs/WINDOWS.md`; testes: `docs/TESTES.md`.
- Auth real: storage/cookies presentes, mas token_fetch falhou em check passivo;
  nenhuma sessao foi renovada nesta verificacao. Fluxo e inventario: `docs/CONFIGURACAO.md`.
- Servidor atualizado apos confirmar ociosidade: API/status com login inativo e
  2 estudos em espera; integracoes/pregacoes/modelo retornaram 200 e HTML usa nlm2.

## Revisao independente do repositorio (19/10/2026)

- Base `5c9549f` confirmada em `origin/main`; 309 testes repetidos em copia isolada (16,41 s).
- Sintaxe Python/JS e XML Android validos; varredura dos 69 arquivos incluidos/alterados sem credenciais detectadas.
- Sem captura, login, upload, envio, reinicio de servicos ou build mobile nesta revisao.
- Reproducoes simuladas identificaram G01/G02; detalhes e G03 na auditoria. Testes verdes nao cobrem essas lacunas.

## Pendencias e proximo passo

1. Proximo passo: corrigir G01 (login pode iniciar apos a guarda e concorrer com pipeline)
   e G02 (PID nao confirma pasta/home da instalacao), com regressoes isoladas.
2. Depois, atualizar pagina e renovar login Google no PC. Ultimo estado registrado
   na sessao anterior: dois estudos em espera; nao reconsultado nesta revisao.
3. Checkpoints do pipeline, retry WhatsApp, metadados no estudo/PDF, formulario
   Flutter e validacao/importacao continuam pendentes (auditoria C/D).
4. Audio real, dois celulares, reconexao e reinicio durante processamento precisam E2E.
5. Fonte Kotlin legada sem Wi-Fi; APK instalado nao atualizado. G03: texto ainda promete
   fallback de disco, mas destino indisponivel bloqueia captura sem troca automatica.
