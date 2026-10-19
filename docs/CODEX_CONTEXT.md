# Pregacao Recorder - contexto operacional

## Inicio

- Projeto: `D:\Dev\pregacao-recorder`; ler este arquivo e `git status --short`.
- Windows: Flask/waitress, SQLite, FFmpeg/DirectShow, painel web e Flutter/MQTT.
- Entrada atual: `iniciar-tudo.bat`; painel `http://127.0.0.1:8080` por padrao.
- Diagnostico sem iniciar: `iniciar-tudo.bat --verificar`; Python atual `.venv\Scripts\python.exe`.
- Instalacao atual ainda e manual; instrucoes em `docs/WINDOWS.md`.
- `.env`, `config/config.json`, tokens, perfis, `data/`, logs e gravacoes sao privados/ignorados.
- Nunca imprimir/commitar segredos ou `docs/CODEX_CONTEXT.local.md` (notas legadas, nao escopo atual).

## Arquitetura e regras

- Gravacao independe de internet/MQTT; celular controla, PC grava/processa.
- Pipeline externo atual: `C:\Users\Aska\Documents\Default Project\sermon-pipeline`.
- Contrato: `PYTHON pipeline.py AUDIO --skip-drive [--to NUMERO]`; logs textuais indicam progresso.
- Upload Drive e estudo sao filas separadas. `rclone` nao e requisito do fluxo integrado.
- Preservar banco, jobs, audios, segmentos e credenciais; testar com home/banco isolados.
- Nao executar migrador legado `_instalador/ajustar_caminhos.py` automaticamente.
- Antes de alterar pipeline/auth/armazenamento, consultar fontes e impacto; nao alterar prompt sem necessidade.
- Auditoria com pendencias: `CONTEXTO_AUDITORIA_PRODUTO.md` (IDs A-G).

## Estado verificado

- Base da revisao: `396240a`, sincronizada com GitHub antes deste planejamento.
- Retirada Raspberry/Linux concluida; inventario em `docs/REMOCAO_RASPBERRY.md`.
- Iniciador unico com filhos ocultos, espera da API e serializacao de cliques implementado.
- FFmpeg/DirectShow; discos Windows; destino ausente bloqueia captura sem fallback.
- Home atual mistura codigo/dados; override `PREGACAO_HOME` suportado.
- Formularios web independentes e controles Linux removidos.
- Login NotebookLM monitorado com sessao nova e auth check passivo antes de retomar jobs.
- Revisao anterior: 309 testes passaram em copia isolada; sintaxe Python/JS e XML Android OK.
- G01: guarda de login nao cobre todo o intervalo ate iniciar pipeline.
- G02: identidade do PID nao confirma pasta/home entre copias com mesmo Python base.
- G03: texto legado ainda promete fallback de disco. Essas tres correcoes estao pendentes.
- Flutter 2.6.0+12 e fonte atual; Kotlin 1.4 legado; release Flutter usa assinatura debug.
- Pipeline externo sem `.git`; manifesto declara `notebooklm`, instalado observado e `notebooklm-py`.
- Pipeline pressupoe `.venv/Scripts` e grava dados junto ao codigo; runtime ainda nao empacotado.
- Leitura para o planejamento nao iniciou servicos, captura, login, upload ou envio.
- Ultima observacao do servidor pertence a sessao anterior: dois estudos em espera por auth;
  nao assumir que esse estado permanece atual sem consultar antes de operar.

## Task atual e proximo passo

- Usuario simplificou: somente ele usara em outro PC Windows, com todas as funcoes atuais.
- Task `PR-DIST-001`: `docs/TASK_DISTRIBUICAO_WINDOWS.md`; indice `docs/SPRINTS.md`.
- Plano anterior de oito sprints foi substituido por tres, nenhuma iniciada:
  1 pacote/dependencias/caminhos; 2 instalador/configuracao/ajustes; 3 teste no destino.
- Usar pasta gravavel por usuario, launcher/CONFIG e APK atuais; mesmas contas/servicos.
- Nao implementar atualizador, CI, migrador, novo assistente, novos recursos Flutter,
  checkpoints ou refatoracoes gerais como condicao desta instalacao pessoal.
- Manter G01/G02 como ajustes pequenos de login/inicio; outros achados so entram se
  impedirem uso das funcoes atuais no pacote ou forem regressoes. Auditoria preservada.
- Nao copiar .venv com remendos nem publicar credenciais; incluir runtimes/pacotes,
  acertar caminhos e fazer novos logins no destino quando necessario.
- Historico/gravacoes antigos nao precisam de migrador; dados do PC original preservados.
- MQTT: ID novo se ambos os PCs puderem operar; preservar antigo somente em substituicao.
- Proximo passo exato: PR-DIST-001.1.1 a 1.4, montar pacote completo de teste.
- Somente planejamento atualizado; nao ha instalador novo nem prova E2E no outro PC.
