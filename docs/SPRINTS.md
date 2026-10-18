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
| Suite de testes | FUNCIONAL | 290 pytest verdes em `tests/` |
| Documentacao tecnica basica | FUNCIONAL | 13 arquivos (docs/ + README + GUIA-USUARIO + site/) |

---

## 2. LACUNAS PENDENTES (classificadas pela auditoria)

| # | Lacuna | Classificacao | Arquivos que serao tocados |
|---|---|---|---|
| L1 | Backup/controle de versionamento (repo sem `.git`) | NAO IMPLEMENTADA | raiz do projeto |
| L2 | Execucao silenciosa completa (ffmpeg consolidacao sem flag; device.py; send.js QR; bats com console/pause) | PARCIAL | `recording/consolidate.py:82`, `audio/device.py:37,232`, `whatsapp/send.js:93`, `iniciar-*.bat` |
| L3 | Instancia unica do servidor e do tray (so o agente tem trava) | PARCIAL | `app/main.py:127-147`, `tray_app/app.py` |
| L4 | Log do agente no Windows sem PREGACAO_LOG_FILE (2 handlers, mesma pasta) | PARCIAL | `iniciar-agente.bat` |
| L5 | Fila de estudos em memoria (`_aguardando` perde jobs no reinicio) | PARCIAL | `app/estudos.py:43-59,262-310` |
| L6 | Job manager persistente (job_id, estados, retomada pos-reinicio) | PARCIAL (uploads ja tem) | `app/db.py`, `app/estudos.py`, `app/main.py` |
| L7 | Estados reais do pipeline (etapa atual por job) | NAO IMPLEMENTADA | novo em `estudos.py` + `db.py` |
| L8 | Barra de progresso no painel web | NAO IMPLEMENTADA | `web/static/app.js`, `routes.py` |
| L9 | Progresso via MQTT (agent hoje descarta tick/upload_progress) | NAO IMPLEMENTADA | `app/remote/agent.py:835-837` |
| L10 | Barra de progresso no APK | NAO IMPLEMENTADA | `flutter/.../tela_principal.dart` |
| L11 | Metadados da pregacao (tabela, form PC, form celular) | NAO IMPLEMENTADA | `app/db.py:18-65`, `routes.py`, `index.html`, `app.js`, `protocolo.dart` |
| L12 | Importacao CSV/XLSX | NAO IMPLEMENTADA | novo `app/importacao.py` + requirements |
| L13 | Associacao programacao x gravacao + snapshot de metadados | NAO IMPLEMENTADA | `app/recording/manager.py`, `estudos.py` |
| L14 | Incorporacao dos metadados ao estudo (bloco de contexto sem tocar no prompt) | NAO IMPLEMENTADA | `sermon-pipeline/pipeline.py` (montagem do payload, nao o prompt) |
| L15 | WhatsApp: sem confirmacao de entrega, sem retry (run check=True aborta) | PARCIAL | `pipeline.py:130,337-347`, `send.js` |
| L16 | Upload Drive: retomada refaz do zero (sem session URI persistida) | PARCIAL | `app/upload/drive.py:354-365` |
| L17 | Testes: rotas /api/estudos, caminho MP3 da consolidacao, pipeline.py sem suite | NAO TESTADA | `tests/`, novo `sermon-pipeline/tests/` |
| L18 | AGUARDANDO nao e State proprio (depende de `detail`) | PARCIAL | `app/states.py` |
| L19 | Docs desatualizados (TESTES.md diz 272; falta manual leigo, fluxogramas, relatorio) | PARCIAL | `docs/` |
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
- [ ] `consolidate.py:82` → CREATE_NO_WINDOW (ffmpeg da cada gravacao)
- [ ] `audio/device.py:37,232` → CREATE_NO_WINDOW (listagem e teste de sinal)
- [ ] `routes.py:136` (systemctl) → CREATE_NO_WINDOW no Windows
- [ ] `iniciar-gravador.bat` / `iniciar-agente.bat`: rodar sem `pause` com
      console minimizado; `iniciar-agente.bat` → setar `PREGACAO_LOG_FILE`
      (resolve 2 handlers na mesma pasta)
- [ ] `send.js:93`: nao abrir janela do QR no fluxo automatico (QR so no
      pareamento manual, acao explicita do operador)
- [ ] Manter JANELA VISIVEL apenas no: login do NotebookLM (excecao oficial)
      e no pareamento manual do WhatsApp
- [ ] Limpeza de `handoff_*.log` antigos + teto para `login_nlm.log`
      (rotacao simples)
- Marcar L2, L4, L6(parcial de logs)
- Testes: 290 verdes + teste unitario das flags de subprocess
- **Prova real**: gravar 1x pelo PC e nao ver NENHUMA janela nova

### S2 - GERENCIADOR PERSISTENTE DE TAREFAS (2-3 dias)  [FASE 2 base]
Objetivo: job_id unico, estados reais, sobrevive a reinicio.
- [ ] Tabela `jobs` no SQLite (`job_id`, `recording_id`, `audio_path`,
      `drive_file_id`, `metadados` snapshot, `estado`, `etapa`, `resultado`,
      `erro`, `tentativas`, timestamps)
- [ ] Estados: PENDENTE / EXECUTANDO / CONCLUIDO / ERRO /
      AGUARDANDO INTERVENCAO / CANCELADO
- [ ] Migrar `estudos.py`: `deque` + `_aguardando` -> banco
      (preservar a logica de pre-flight/keepalive ja testada)
- [ ] Recuperacao no boot (`app/main.py`): jobs incompletos voltam para fila
- [ ] Idempotencia: etapa concluida nunca re-executa (checar por resultado
      gravado, nao por estado de memoria)
- Marcar L5, L6, L7 (estado/etapa ja persistem)
- Testes: novos em `test_estudos.py`/`test_db.py` (reinicio com jobs na fila,
  nao-duplicacao de etapa)
- **Nao fazer**: UI de progresso (S3) - primeiro o dado, depois a barra

### S3 - BARRA DE PROGRESSO PC + MQTT + APK (2-3 dias)  [FASE 2 restante]
Objetivo: o operador ve a etapa real no PC e no celular.
- [ ] `estudos.py` emite marcos REAIS por job (etapa 1..7 do prompt,
      percentual so por marco concluido, nunca por tempo; 100% so com
      WhatsApp confirmado)
- [ ] Payload MQTT por job: `job_id`, `etapa`, `estado`, `percentual`,
      `descricao`, `timestamp`, `versao/seq` (descartar sequencias antigas)
- [ ] `agent.py`: deixar de descartar progresso (`:835-837`), publicar
      estado de job com retain apropriado (comando nunca retain)
- [ ] Painel web: barra/etapas por job (verde/executando/pendente/amarelo/vermelho)
- [ ] APK: secao de progresso lendo o mesmo topico (compat iOS intacto)
- [ ] Reconectar/abrir APK recebe estado atual sem reiniciar nada
- [ ] Painel /config: area **SAÚDE DAS INTEGRAÇÕES** (Drive, NotebookLM,
      WhatsApp, EMQX) com estados padrao (Conectado/NaO configurado/
      Verificando/Autenticacao necessaria/Erro), ultima verificacao,
      resultado real, diagnostico e acao necessaria (prompt item 8 -
      estava fora do plano; adicionado na revisao de 18/10)
- Marcar L8, L9, L10
- Testes: agent (payloads novos), app.js via teste de rota, Flutter
  `protocolo_test.dart`
- **Prova real**: 2 celulares mostrando a mesma etapa + reconexao MQTT

### S4 - DADOS DA PREGACAO: METADADOS + FORM + PLANILHA (3-4 dias)  [FASE 3]
Objetivo: camada de metadados unica, no PC, refletida no celular.
- [ ] Tabela `pregacoes` (data, horario, pregador, igreja, texto_base, tema)
      em `app/db.py` - reaproveitar colunas de `sessions` existentes se houver
- [ ] Form no painel web (`index.html` + `app.js`) com validacao
- [ ] Form/edicao no APK via MQTT (mesmo topico de dados, versao por registro
      para evitar sobrescrita) - nenhum celular guarda base propria
- [ ] Importador CSV/XLSX (`app/importacao.py` + openpyxl): validar, previa,
      detectar duplicatas, confirmar, gravar no SQLite
- [ ] Associacao programacao x gravacao no start (match data+horario;
      ambiguidade -> pedir confirmacao)
- [ ] Snapshot dos metadados no `job_id` ao iniciar o estudo (congelamento)
- Marcar L11, L12, L13
- Testes: db, rotas, importador (CSV e XLSX de exemplo em `tests/fixtures/`)
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
