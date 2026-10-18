# PREGACAO RECORDER - PLANO DE SPRINTS

Auditoria feita em 18/10/2026 sobre o codigo real (nao sobre documentacao).
Cada feature tem UM dono de sprint - nunca dois sprints tocam na mesma funcao
em paralelo (regra anti-retrabalho).

Classificacao: FUNCIONAL / PARCIAL / COM ERRO / NAO IMPLEMENTADA / NAO TESTADA.

---

## 1. O QUE JA ESTA FECHADO (NAO REFACER)

| Feature | Estado | Evidencia |
|---|---|---|
| Gravacao PC (captura, dispositivos, offline) | FUNCIONAL | `app/audio/recorder.py`, `app/recording/manager.py`, 41 testes |
| Consolidacao MP3 | FUNCIONAL (ramo MP3 sem teste) | `app/recording/consolidate.py` |
| Upload Drive + OAuth em producao + fila persistente | FUNCIONAL | `app/upload/drive.py`, `app/upload/queue.py`, `app/db.py` |
| Autenticacao NotebookLM (pre-flight, AGUARDANDO, retomada, keepalive, login automatico) | FUNCIONAL | `app/estudos.py`, 14 testes, provado ao vivo 18/10 |
| Rotas /api/estudos/* + card no /config + botoes diagnosticar/reconectar | FUNCIONAL | `app/api/routes.py:780-816`, `web/` |
| Pipeline estudo + PDF + WhatsApp (E2E) | FUNCIONAL (sem teste automatizado) | `sermon-pipeline/pipeline.py`, 2 PDFs enviados em 18/10 |
| Prompt original preservado | FUNCIONAL | `sermon-pipeline/prompt.txt` intocado |
| MQTT/TLS EMQX (ACK, reconexao, LWT, trava de instancia) | FUNCIONAL | `app/remote/agent.py`, 62 testes |
| APK Flutter 2.5.0+11 (controle, status, cronometro) | FUNCIONAL | `flutter/pregacao_controle/` |
| SQLite local (sessions/uploads/events) + logs rotativos no app | FUNCIONAL | `app/db.py`, `app/logging_setup.py` |
| Suite de testes | FUNCIONAL | 317 pytest verdes em `tests/` (18/10) |
| Documentacao tecnica basica | FUNCIONAL | 13 arquivos (docs/ + README + GUIA-USUARIO + site/) |

---

## 2. LACUNAS PENDENTES (classificadas pela auditoria)

| # | Lacuna | Classificacao | Arquivos que serao tocados |
|---|---|---|---|
| L1 | Backup/controle de versionamento (repo sem `.git`) | IMPLEMENTADA (S0) | commit `78f6969` + repo GitHub; zips em `D:\Dev\backups\` |
| L2 | Execucao silenciosa completa (ffmpeg consolidacao sem flag; device.py; send.js QR; bats com console/pause) | IMPLEMENTADA (S1) | `recording/consolidate.py`, `audio/device.py`, `routes.py`, `whatsapp/send.js`, `iniciar-*.bat` |
| L3 | Instancia unica do servidor e do tray (so o agente tem trava) | IMPLEMENTADA (S0) | `app/main.py:127-147`, `tray_app/app.py` |
| L4 | Log do agente no Windows sem PREGACAO_LOG_FILE (2 handlers, mesma pasta) | IMPLEMENTADA (S1) | `iniciar-agente.bat` → `logs/pregacao-agente.log` (provado) |
| L5 | Fila de estudos em memoria (`_aguardando` perde jobs no reinicio) | IMPLEMENTADA (S2) | `app/estudos.py` + tabela `jobs` em `app/db.py` |
| L6 | Job manager persistente (job_id, estados, retomada pos-reinicio) | IMPLEMENTADA (S2) | `app/db.py` (jobs + guards), `app/estudos.py`, `app/main.py` (boot) |
| L7 | Estados reais do pipeline (etapa atual por job) | PARCIAL (S2: dado; S3: exibir) | `etapa` persistida por job em `db.py`; API/UI na S3 |
| L8 | Barra de progresso no painel web | IMPLEMENTADA (S3) | `web/templates/index.html`, `web/static/app.js`, `web/static/style.css` |
| L9 | Progresso via MQTT (agent hoje descarta tick/upload_progress) | IMPLEMENTADA (S3) | `app/remote/agent.py` (topic `jobs` retido + `_publica_job` guarda seq) |
| L10 | Barra de progresso no APK | IMPLEMENTADA (S3) | `flutter/.../protocolo.dart` (ProgressoJob), `mqtt_controlador.dart`, `tela_principal.dart` |
| L11 | Metadados da pregacao (tabela, form PC, form celular) | IMPLEMENTADA (S4) | `app/db.py` (tabela `pregacoes`), `web/templates/index.html` + `app.js`, `protocolo.dart` (Pregacao) |
| L12 | Importacao CSV/XLSX | IMPLEMENTADA (S4) | `app/importacao.py` + openpyxl, `routes.py` (/api/importacao/*), `web/templates/index.html` + `app.js` |
| L13 | Associacao programacao x gravacao + snapshot de metadados | IMPLEMENTADA (S4) | `app/estudos.py` (snapshot_pregacao_para_job no _rodar), `db.py` |
| L14 | Incorporacao dos metadados ao estudo (bloco de contexto sem tocar no prompt) | NAO IMPLEMENTADA | `sermon-pipeline/pipeline.py` (montagem do payload, nao o prompt) |
| L15 | WhatsApp: sem confirmacao de entrega, sem retry (run check=True aborta) | PARCIAL | `pipeline.py:130,337-347`, `send.js` |
| L16 | Upload Drive: retomada refaz do zero (sem session URI persistida) | PARCIAL | `app/upload/drive.py:354-365` |
| L17 | Testes: rotas /api/estudos, caminho MP3 da consolidacao, pipeline.py sem suite | NAO TESTADA | `tests/`, novo `sermon-pipeline/tests/` |
| L18 | AGUARDANDO nao e State proprio (depende de `detail`) | PARCIAL | `app/states.py` |
| L19 | Docs desatualizados (TESTES.md dizia 272; falta manual leigo, fluxogramas, relatorio) | PARCIAL (DOC A pronto) | `docs/` - TESTES.md sincronizado (301), `PREGACAO-COMO-FUNCIONA.md/.pdf` entregues; faltam DOC B-E |
| L20 | Dois APKs divergentes (2.5 Flutter vs 1.4 Kotlin legado) | RISCO | `android/` legado |

---

## 3. SPRINTS

### S0 - FUNDACAO E SEGURANCA (1 dia)  [antecede tudo - regra 19]
Objetivo: nunca mais perder trabalho; base para alteracoes estruturais.
- [x] `git init` + `.gitignore` (excluir `.env`, `config/*.json` com segredo,
      `whatsapp/auth/`, `recordings/`, `.venv/`, `node_modules/`) + commit inicial
      -> repo `marcellolabr3/pregacao-recorder` (publico), commit `78f6969`
- [x] Backup zip datado de `sermon-pipeline` + `pregacao-recorder` (fora do repo)
      -> `D:\Dev\backups\*_2026-10-18_1237.zip`
- [x] Trava de instancia unica no servidor (`app/main.py`) reaproveitando
      `TravaInstancia` de `app/remote/agent.py:981` e no tray do pipeline
      (`tray_app/app.py`, trava nova por pid - entra em vigor no proximo boot)
- [x] Sincronizar `docs/TESTES.md` (292) e registrar a auditoria (este arquivo)
- Marcar L1, L3, parte de L19
- Testes: 292 verdes + `tests/test_main.py` (2 testes de trava)
- **Nao fazer**: nenhuma feature nova nesta sprint

### S1 - EXECUCAO SILENCIOSA E LOGS (1-2 dias)  [FASE 1 do prompt]
Objetivo: zero janelas indevidas na operacao normal.
- [x] `consolidate.py` → CREATE_NO_WINDOW (ffmpeg de cada gravacao)
- [x] `audio/device.py` (`_run` listagem + teste de sinal) → CREATE_NO_WINDOW
- [x] `routes.py` (systemctl) → CREATE_NO_WINDOW no Windows
- [x] `iniciar-gravador.bat` / `iniciar-agente.bat`: `pause` SO em ERRO
      (fluxo normal fecha sozinho); `iniciar-agente.bat` →
      `PREGACAO_LOG_FILE=pregacao-agente.log` (resolve 2 handlers na mesma
      pasta - provado: a recusa da 2a instancia gravou no log proprio)
- [x] `send.js` (sermon-pipeline): imagem do QR abre so no pareamento
      manual (`--login`); o fluxo automatico so registra o caminho
- [x] JANELA VISIVEL mantida apenas no: login do NotebookLM (excecao
      oficial) e no pareamento manual do WhatsApp
- [x] Limpeza de `handoff_*.log` (so os 30 mais novos) + `login_nlm.log`
      rotativo (2 MB x 3), rodando dentro do vigia periodico
- [x] Marcar L2 e L4 como IMPLEMENTADAS na tabela de lacunas
      (L6 permanece PARCIAL - job manager e S2)
- [x] Testes: **301 verdes** (exit 0) + `tests/test_silencio.py` (7 testes
      de flag/housekeeping); `docs/TESTES.md` sincronizado em 301
- [x] **Prova real 18/10 14:26**: gravacao com TTS via `/api/start` +
      `/api/stop` (IDLE→RECORDING→FINALIZING→COMPLETED) → **7 execucoes
      de ffmpeg, todas com `MainWindowHandle=0`; 0 janelas novas**; MP3
      de 180,9 KB em `recordings/2026/10/`. Troca do painel para o codigo
      S1 (pid 44132) tambem sem janela nova. Prova do `.bat` em erro:
      `pause` + log proprio.
- Commit `5ab2515` (push ok); backup `sermon-pipeline_2026-10-18_1429.zip`
      renovado (inclui o `send.js` alterado)

### S2 - GERENCIADOR PERSISTENTE DE TAREFAS (2-3 dias)  [FASE 2 base]
Objetivo: job_id unico, estados reais, sobrevive a reinicio.
- [x] Tabela `jobs` no SQLite (`job_id`, `recording_id`, `audio_path`,
      `drive_file_id`, `metadados` snapshot, `estado`, `etapa`, `resultado`,
      `erro`, `tentativas`, `created/updated/started/finished_at`)
- [x] Estados: PENDENTE / EXECUTANDO / CONCLUIDO / ERRO /
      AGUARDANDO_INTERVENCAO / CANCELADO - todas as trocas passam por
      transicao COM GUARDA no estado atual (testado)
- [x] Migrar `estudos.py`: `deque` + `_aguardando` -> banco
      (pre-flight/keepalive preservados - os 14 testes originais seguem
      verdes, adaptados so para o banco isolado por teste)
- [x] Recuperacao no boot: `retomar_apos_reinicio()` chamada por
      `iniciar()` (subida do painel via `main.py` -> `register_routes`);
      EXECUTANDO volta a PENDENTE **a nao ser que o log de handoff prove
      `=== CONCLUIDO`** (prova gravada, nao memoria)
- [x] Idempotencia: `audio_path` UNIQUE (enfileirar duplo = 1 job),
      guarda de estado em concluir/falhar/aguardar/reenfileirar, etapa
      concluida nunca re-executa nem e sobrescrita por falha atrasada
- [x] Acordamento: `diagnosticar()` e o vigia periodico puxam PENDENTE
      esquecido (nao espera a proxima gravacao)
- [x] Marcar L5, L6 como IMPLEMENTADAS e L7 como PARCIAL (etapa ja
      persiste por job; a exposicao na API/UI e da S3)
- [x] Testes: novo `tests/test_jobs.py` (16 testes: guards, boot,
      acordamento, enfileirar duplo) + `test_estudos.py` adaptado;
      **317 verdes, exit 0**
- [x] **Prova real 18/10 14:49**: job EXECUTANDO orfao criado com o
      painel FORA -> painel subiu com S2 -> recuperacao devolveu a fila
      -> pre-flight real -> AGUARDANDO_INTERVENCAO com motivo; linha no
      banco com `recording_id` + `drive_file_id` snapshot (upload ao
      Drive congelado), `tentativas=2`, zero janelas novas
- **Nao fazer**: UI de progresso (S3) - primeiro o dado, depois a barra
  (respeitado: nenhuma rota/UI nova nesta sprint)

### S3 - BARRA DE PROGRESSO PC + MQTT + APK (2-3 dias)  [FASE 2 restante]
Objetivo: o operador ve a etapa real no PC e no celular.
- [x] `estudos.py` emite marcos REAIS por job (etapa 1..7 do prompt,
      percentual so por marco concluido, nunca por tempo; 100% so com
      WhatsApp confirmado) — `_publicar_job`, `_drenar_log`, `_marcos_concluidos`
- [x] Payload MQTT por job: `job_id`, `etapa`, `estado`, `percentual`,
      `descricao`, `timestamp`, `seq` monotona (descartar sequencias antigas)
- [x] `agent.py`: deixar de descartar progresso (`:835-837`), publicar
      estado de job no topic `jobs` retido (comando nunca retain)
- [x] Painel web: barra/etapas por job (verde/executando/pendente/amarelo/vermelho)
- [x] APK: secao de progresso lendo o mesmo topico (compat iOS intacto)
- [x] Reconectar/abrir APK recebe estado atual sem reiniciar nada (retido)
- [x] Painel /config: area **SAÚDE DAS INTEGRACOES** (Drive, NotebookLM,
      WhatsApp, EMQX) com estados padrao (Conectado/NaO configurado/
      Verificando/Autenticacao necessaria/Erro), ultima verificacao,
      resultado real, diagnostico e acao necessaria (prompt item 8)
- Marcar L8, L9, L10 ✅
- Testes: agent (4 novos), jobs (8 novos), Flutter `protocolo_test.dart` (9 novos)
- **Prova real**: pendente (aguarda sessao NotebookLM renovada + 2 celulares + reconexao MQTT)

### S4 - DADOS DA PREGACAO: METADADOS + FORM + PLANILHA (3-4 dias)  [FASE 3]
Objetivo: camada de metadados unica, no PC, refletida no celular.
- [x] Tabela `pregacoes` (data, horario, pregador, igreja, texto_base, tema)
      em `app/db.py` com indice unico (data+horario) e versao otimista
- [x] Form no painel web (`index.html` + `app.js`) com validacao (CRUD + modal importacao)
- [x] Form/edicao no APK via MQTT (`protocolo.dart`: `Pregacao`, `ComandoPregacao`)
- [x] Importador CSV/XLSX (`app/importacao.py` + openpyxl): validar, previa,
      detectar duplicatas, confirmar, gravar no SQLite
- [x] Associacao programacao x gravacao no start (match data+horario da sessao)
- [x] Snapshot dos metadados no `job_id` ao iniciar o estudo (congelamento em `jobs.metadados`)
- Marcar L11, L12, L13 ✅
- Testes: db, rotas, importador (13 testes em `test_importacao.py` + 9 Flutter)
- **Nao fazer**: nada de NotebookLM nesta sprint

### S5 - ESTUDO COM METADADOS + WHATSAPP (2 dias)  [FASE 4-5]
Objetivo: documento de identificacao + envio sem duplicar.
- [ ] Pipeline: montar bloco `DADOS DA PREGACAO` a partir do snapshot do job
      e entregar AO PROMPT como contexto adicional - **prompt.txt nao muda**
- [ ] PDF: cabecalho/identificacao do job correto (job_id no nome ou meta)
- [ ] WhatsApp: distinguir preparado/solicitado/aceito/enviado (Baileys
      `sendMessage` resolve = aceito; sem mentir "entregue")
- [ ] Retry do envio sem duplicar (checar se o job ja enviou - estado no job)
- [ ] `pipeline.py:130`: falha de envio vira etapa AGUARDANDO INTERVENCAO,
      nao aborta o job inteiro
- Marcar L14, L15
- Testes: `sermon-pipeline/tests/` (montagem do payload com snapshot; PDF)
- **Prova real**: 1 E2E completo com metadados preenchidos no celular

### S6 - RESILIENCIA RESTANTE + E2E DE DOMINGO (1-2 dias + domingo)  [FASE 5]
Objetivo: fechar as lacunas de resiliencia com prova real.
- [ ] Upload Drive retomavel com session URI persistida (L16)
- [ ] `AGUARDANDO INTERVENCAO` como State proprio (L18), visivel no APK
- [ ] Teste E2E real: gravar pelo celular no domingo ->
      MP3 -> Drive -> NotebookLM -> PDF -> WhatsApp
- [ ] Teste de queda: reiniciar o PC no meio do processamento -> retomada
      do job pela etapa pendente
- [ ] Testes de regressao completos (pytest + flutter test)
- [ ] APK final (nova versao 2.6) so apos validacao; apagar/ignorar o APK
      Kotlin legado 1.4 (L20)
- Testes automatizados vs simulados vs reais documentados

### S7 - DOCUMENTACAO COMPLETA (3-4 dias)  [FASE 6 - obrigatorio]
Objetivo: entrega para leigos + manutencao + relatorio final.
- [x] DOC A: `docs/PREGACAO-COMO-FUNCIONA.md` (leigo:13 secoes, fluxogramas,
      tabela de tecnologias, o que pronto/pendente) - **concluido em 18/10**:
      fonte Markdown + `docs/PREGACAO-COMO-FUNCIONA.pdf` (7 paginas, gerado
      por `scripts/md_para_pdf.py`) + exemplo visual da barra de progresso
- [ ] DOC B: manual do operador (atualizar/expandir `GUIA-USUARIO.md`) - PDF,
      so com screenshots reais
- [ ] DOC C: documentacao tecnica (atualizar `docs/` + `DOCUMENTACAO.md`:
      novos jobs, estados, MQTT de progresso, importador)
- [ ] DOC D: fluxogramas Mermaid (12 pedidos) com fonte `.mmd` + export PNG/SVG
- [ ] DOC E: relatorio de implementacao (alteracoes reais vs sugestao,
      testes executados e resultados, limitacoes conhecidas)
- [ ] Atualizar `docs/TESTES.md`, `CHECKLIST.md`, `README.md`
- [ ] Limitacao declarada com honestidade: expiracao do NotebookLM nao foi
      eliminada para sempre (so reduzida e blindada)
- Regra 14/15: nenhum documento afirma feature sem teste correspondente

---

## 4. ORDEM E DEPENDENCIAS

```
S0 (backup/trava)  ->  S1 (silencioso)  ->  S2 (job manager)
                                              |
                        +---------------------+---------------------+
                        v                                           v
                 S3 (progresso)                              S4 (metadados)
                        |                                           |
                        +---------------------+---------------------+
                                              v
                                    S5 (estudo+whatsapp)
                                              v
                                    S6 (E2E real + regressao)
                                              v
                                    S7 (documentacao)
```

- S1 e S4 podem trocar de ordem se o domingo chegar antes (S1 e rapida).
- S3 SEM S2 primeiro = retrabalho (barra sem job_id/etapa persistida).
- S5 SEM S4 = retrabalho (incorporar metadados inexistentes).
- S7 sempre por ultimo, mas o RELATORIO de cada sprint e anotado no dia
  (regra: registrar o que foi implementado/testado/pendente ao concluir).

## 5. DEFINICAO DE PRONTO DE CADA SPRINT

1. Codigo commitado (S0 em diante)
2. `pytest tests` verde sem regressao (+ testes novos da sprint)
3. Prova real da sprint registrada (comando/log evidencia) OU motivo declarado
4. `docs/` atualizado no ponto tocado
5. Nenhuma funcionalidade previa quebrada (gravacao + upload + estudo seguem OK)
