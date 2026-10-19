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

- Usuario pediu plano para exportar/instalar em outros PCs Windows.
- Task `PR-DIST-001`: `docs/TASK_DISTRIBUICAO_WINDOWS.md`; indice em `docs/SPRINTS.md`.
- Oito sprints planejadas, nenhuma implementada: 1 inventario/build; 2 correcoes;
  3 runtime/caminhos; 4 instalador/assistente; 5 resiliencia; 6 backup/update;
  7 homologacao/release; 8 funcionalidades restantes.
- Primeiro instalador candidato na 4; liberacao homologada ate a 7. A 8 e evolucao funcional.
- Proximo passo exato: PR-DIST-001.1.1 a 1.6, inventariar/versionar pipeline e provar
  dependencias/empacotamento em ambiente limpo. Depois executar sprint 2.
- D01-D15 e C01-C16 continuam pendentes conforme mapeamento da task; nao marcar
  persistencia de job como checkpoint nem modelos Flutter como formulario pronto.
- Documento de planejamento criado; nao ha instalador novo ou garantia E2E pronta.
