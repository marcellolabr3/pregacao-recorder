# Pregacao Recorder - contexto operacional

## Inicio

- Projeto: `D:\Dev\pregacao-recorder`; ler este arquivo e `git status --short`.
- Windows x64: Flask/waitress, SQLite, FFmpeg/DirectShow, painel e Flutter/MQTT.
- Desenvolvimento: `iniciar-tudo.bat`, `.venv\Scripts\python.exe`, painel 127.0.0.1:8080.
- Diagnostico somente leitura: `iniciar-tudo.bat --verificar`.
- `.env`, configuracao pessoal, tokens/perfis, banco, logs e gravacoes nunca entram no Git.
- `docs/CODEX_CONTEXT.local.md` contem legado sensivel; nunca imprimir/commitar.

## Ciclo atual - WhatsApp, desligamento e mapa mental (20/10/2026)

- Escopo e aceite: [TASKS_SPRINTS_20261020_ENTREGA.md](TASKS_SPRINTS_20261020_ENTREGA.md).
  Sprints 1 a 4 enviadas em `ecf2df6`, `e81017b`, `a1bad7e`, `2dc4b85`.
  Ajuste de migracao e acesso ao mapa sem PDF em `f29c77c`.
  **Nao gerar APK, instalador, pacote ou atualizador** ate o usuario pedir
  expressamente, mesmo apos todos os testes passarem. Commit/push por sprint.
- O usuario esclareceu: **APK sem PIN/senha de acesso; MQTT conserva senha e
  token como ja configurados**. Nao mudar broker nem retirar autenticacao MQTT.
- WhatsApp: o app antigo confundia o marcador `8. Enviando` com entrega.
  Agora apenas `ACEITO_PELO_SERVIDOR` (ID devolvido por Baileys) e comprovado;
  nenhuma mensagem e rotulada como entregue ao telefone. Estados antigos
  `FINAL` sao legado de prova incerta. CONFIG mostra destinos salvos, conexao
  local/QR, verificacao, reenvio do PDF existente e resultados por numero.
- Diagnostico do outro PC sem SSD: a sessao e local em
  `PREGACAO_PIPELINE_HOME/whatsapp/auth`; sem o log daquele PC, nao ha como
  afirmar o motivo exato. O usuario foi consultado pelas linhas do log.
- No laboratorio, o codigo atualizado esta em `vendor/sermon-pipeline`; a
  configuracao ignorada pelo Git foi apontada para ele. `.env` local direciona
  `PREGACAO_PIPELINE_HOME` e `NODE_PATH` a instalacao local antiga, preservando
  login, output e dependencias ja existentes sem copia-los. O CLI local e
  NotebookLM 0.8.5. `send.js --status` conectou ao WhatsApp real, sem enviar
  mensagem, usando o codigo novo. Nunca imprimir ou commitar QR/auth/.env.
- Desligamento: opcao desligada por padrao, atraso 1..1440 minutos. Monitor
  so arma apos atividade ou clique explicito; bloqueia enquanto ha gravacao,
  recuperacao, upload, estudo ou reenvio pendente. Uma nova atividade zera o
  prazo. Comando Windows ocorre apenas no fim da contagem. Testes o simulam.
- Mapa mental: opcional, instrucoes em CONFIG, geracao `interactive` no mesmo
  notebook via CLI 0.8.5, salva JSON em `output`, visualiza e baixa no painel.
  Falha opcional e informada sem impedir o envio do PDF. Formato imagem/PDF
  ainda nao foi pedido. Nenhuma geracao real foi feita neste ciclo.
- Suite Python completa e sintaxe JS passaram apos as mudancas de fonte. Nao
  foi feito envio real nem desligamento real. Aceite no outro PC/SSD continua
  pendente por falta de acesso fisico.
- Integracao no laboratorio: `app.launcher --sem-navegador` reiniciou gravador
  e agente depois de confirmar IDLE e filas vazias; nova chamada reconheceu os
  dois como ja em execucao. API mostrou controles novos, desligamento desativado,
  WhatsApp verificado via `/api/whatsapp/check` e MQTT conectado. O launcher
  agora aceita `pythonw.exe` do mesmo Python base quando consultado por
  `python.exe`, sempre conferindo os marcadores absolutos de instalacao/home.
  Suite Python completa passou apos esse ajuste.
- O codigo Flutter do protocolo agora trata `FINAL` legado como envio incerto e
  `FINAL_ACEITO` como aceite pelo servidor, sem comprovacao de entrega. Os 37
  testes de `test/protocolo_test.dart` passaram; o APK instalado permanece antigo
  ate novo build solicitado pelo usuario.

## Ciclo anterior - 20/10/2026

- Pedido e tarefas: [TASKS_SPRINTS_20261020.md](TASKS_SPRINTS_20261020.md).
  Commits ja enviados: sprint 1 `a3977a9`, sprint 2 `0ae930a`, sprint 3
  `c9f2fea`, sprint 4 `812ed1c`. Gerar APK/pacotes finais so apos fechar
  todas as alteracoes de fonte; commitar cada sprint.
- O usuario confirmou que o APK estabilizou depois de encerrar o agente do
  laboratorio que compartilhava o ClientID MQTT com o SSD. `config/config.json`
  local e ignorado pelo Git e agora usa `pregacao-lab-aska` em Config e
  RemoteSettings; a instalacao real conserva `pregacao-igreja-01`. Nao copiar
  config/estado privado do laboratorio para o SSD.
- O laboratorio funciona sem o SSD: o inicio automatico do usuario Windows foi
  registrado por `packaging/windows_autostart.ps1 -Mode Register -Layout Lab`
  e resolve o volume por numero de serie, nao por letra. Uma abertura real
  iniciou painel/agente; a segunda nao duplicou PIDs. Painel respondeu em
  127.0.0.1:8080 com estado IDLE e a programacao respondeu. Servicos foram
  parados durante a suite e reiniciados ao final; painel/agente estao ativos.
- Sprint 2: tarefa `CONCLUIDO` exibe 100% mesmo quando envio opcional foi
  pulado; etapas puladas continuam identificadas. Snapshot MQTT retido se
  corrige na reconexao. Sprint 3: programacao na pagina inicial do PC/APK,
  CRUD por MQTT, versao otimista para dois celulares, eventos de atualizacao;
  nenhum PIN e solicitado no APK para essa operacao. O agente usa somente as
  credenciais administrativas locais do PC.
- Flutter 2.7.0+13 esta preparado em `pubspec.yaml`. Ainda falta gerar e
  conferir o APK. Os testes Python direcionados (141), protocolo Flutter
  (35), analise Flutter e a suite Python completa passaram. As duas goldens
  da pagina principal precisam ser atualizadas para a nova programacao.
- Sprint 4: `personal_update.iss`/`build_personal_update.py` geram um
  atualizador que aceita so a pasta pessoal existente, faz backup dos
  arquivos publicos dentro dela e preserva banco, contas, perfis e audios.
  O instalador pessoal e o atualizador registram o inicio automatico com
  resolucao por volume. O helper oferece Status/Enable/Disable e espera ate
  60 segundos pelo SSD no logon. Falta compilar/testar o atualizador.
- O SSD esta no outro PC. O usuario conseguiu entrar no NotebookLM la.
  Nao ha acesso daqui para conferir/remover a pasta antiga, aplicar o
  atualizador ou testar os dois celulares. O usuario autorizou eliminar
  pastas antigas do SSD quando ele estiver acessivel, preservando a pasta
  pessoal. Nao declarar aceite real antes dessa prova.
- O instalador pessoal antigo pode restaurar o snapshot de 20/10, mas nao deve
  ser regenerado daqui: `build_personal_portable.py` incorpora contas e dados
  da maquina de build. Entregar atualizador sem estado privado no ciclo atual.
- Ferramentas: Flutter `D:\Dev\flutter-sdk\flutter\bin\flutter.bat`, Python
  `.venv\Scripts\python.exe`, Inno
  `.bundle-cache\inno-7.1.0\compiler\ISCC.exe`.

## Arquitetura e regras

- Gravacao local independe de internet/MQTT; PC processa, celular controla.
- Upload Drive e estudo sao filas independentes; contrato `pipeline.py AUDIO --skip-drive [--to NUMERO]`.
- Desenvolvimento preserva pipeline externo configurado; fonte original em
  `C:\Users\Aska\Documents\Default Project\sermon-pipeline` nao foi alterada.
- Pacote usa fontes minimas em `vendor/sermon-pipeline/`, prompt preservado e SOURCE.json.
- Preservar dados/jobs/credenciais; testes somente com homes e bancos isolados.
- Orientacao explicita do usuario (20/10/2026): ao encontrar uma limitacao,
  consultar o usuario antes de escolher uma alternativa ou pedir permissao
  para a acao impedida. Nao presumir consentimento pelo silencio.
- Nao executar `_instalador/ajustar_caminhos.py` nem copiar .venv com remendos.
- Auditoria e limites: `CONTEXTO_AUDITORIA_PRODUTO.md` (IDs A-G).
- Configurar audio/pasta com gravador ocioso; alteracao de destino durante captura e risco preexistente nao corrigido nesta entrega.

## Registro anterior: pacote generico validado (19-20/10/2026)

- PR-DIST-001: implementacao dos fluxos da sprint 2 concluida; aceite pessoal 2.2/2.3 no destino pendente.
- Sprint 3 iniciada: 11 provas isoladas do instalador passaram; Windows limpo/hardware/contas/celular reais pendentes.
- Suite completa: 488 testes passaram em 42,17s em copia somente de fontes publicas, sem credenciais/dados reais.
- JS e `git diff --check` passaram; o artefato foi montado a partir do snapshot `96add70-dirty`.
- Audio: `/api/audio/test` testa device/taxa/canais selecionados sem salvar; overrides exigem admin; interface ausente e recusada.
- CONFIG valida o lote antes de aplicar/criar pasta; `Config.update_and_save` restaura memoria se a escrita falhar.
- MQTT: `POST /api/remote/config` administrativo permite configurar pelo cartao existente; senha nunca sai, token mascarado/admin.
- Senha/token vazios preservam; bloco `remote` salvo prevalece sobre `.env`; ID unico em Config/RemoteSettings/topics/launcher.
- MQTT exige ociosidade para salvar; aplicar exige reiniciar servicos (guia: reiniciar Windows e abrir atalho).
- Fechar somente o navegador nao reinicia; heartbeat antigo nao confirma configuracao pendente.
- Drive/NotebookLM ja possuem conexao/renovacao no painel; WhatsApp usa `Conectar WhatsApp.cmd`, sem envio no pareamento.
- Instalador Inno7 por usuario em `%LOCALAPPDATA%\PregacaoRecorder`, atalho unico, sem iniciar processos ao instalar.
- Reinstalacao preserva dados e faz backup sem duplicar audios; recusa processo ativo/lock/junction. Desinstalacao preserva dados.
- Bootstrap gera segredo/ID persistentes; preserva PINs/preferencias/ID explicito. Homes do pipeline/NotebookLM locais ao pacote.
- G01/G02 implementados: perfil reservado ate filho sair e PID identificado por raiz/home; nao matar processo estranho.
- Runtimes privados: Python3.11.9, 62 distribuicoes, Node24.18.0, FFmpeg/ffprobe, Chromium e headless shell.
- Instalador atual: `dist-pacote/PregacaoRecorder-Instalar-sprint2-20261020T000353363243Z.exe`, 515,9 MiB; `.exe.sha256` conferido.
- Pacote correspondente: `dist-pacote/PregacaoRecorder-sprint2-20261020T000353363243Z/`; 7.858 arquivos, zero extras, 50 fontes/guia/vendor conferidos.
- Smoke completo de runtimes passou; compilacao Inno passou. `.bundle-cache/sprint2-current-artifact.json` registra metadados publicos.
- Smoke UI Chromium privado offline passou: primeiro uso, audio/pasta, MQTT, segredos e reabertura; `.bundle-cache/sprint3-config-ui-final.log`.
- Payload real instalado em pasta temporaria com espacos/acentos/&: 7.858 hashes conferidos, diagnostico com PATH isolado e CONFIG persistida em processo novo passaram.
- Evidencia final da instalacao: `.bundle-cache/sprint3-full-install-20261020T001205Z/report.json`; hardware/contas simulados, sem registro/atalho pessoal.
- Primeiro destino de teste era profundo demais (arquivo de 264 caracteres falhou na leitura Python comum); repetir em pasta curta passou. Preferir caminho padrao do instalador.
- Guias: `docs/GUIA_INSTALACAO_WINDOWS.md`, `docs/ACEITE_WINDOWS.md`; build `packaging/README.md`.
- Fontes-chave: `app/api/routes.py`, `app/config.py`, `app/audio/device.py`, `app/remote/settings.py`, `app/remote/agent.py`,
  `app/launcher.py`, `app/bundled_runtime.py`, `web/static/app.js`, `web/templates/index.html`, `packaging/build_*.py`.
- Evidencias: `docs/TESTES.md`, `.bundle-cache/sprint2-isolated-pytest.json`, `.bundle-cache/sprint3-installer-fixtures-20261019/`.

## Registro anterior: edicao pessoal no SSD (20/10/2026)

- Apos a limpeza anterior, `E:\PregacaoRecorder-Pessoal` nao estava mais no SSD;
  a pasta antiga `E:\PregacaoRecorder` havia reaparecido incompleta. A causa da
  mudanca ainda nao foi identificada. O instalador privado foi copiado para a
  raiz do SSD e executado de la com codigo 0, restaurando a pasta pessoal.
- O instalador `PregacaoRecorder-Pessoal-Instalar-portable-20261020T011738Z.exe`
  no SSD tem SHA-256 `6EA5BE07A137EB7DDFC1BC3DA1E5A0053A2F9FAD4EBC0D00AE89BA4BEC15B48C`;
  seu `.exe.sha256` tambem esta no SSD. Uma copia privada permanece em `dist-pacote/`.
- `verify_personal_portable.py` confirmou 7.859 arquivos publicos e 6.236
  privados. `Verificar Pacote.cmd` e o diagnostico do runtime passaram. O banco
  passou em `integrity_check`: 12 sessoes, 12 uploads concluidos e 2 estudos
  concluidos. O primeiro inicio realocou config, banco e caminhos historicos
  para `E:`. A captura de teste no microfone Logi C270 gravou 2 segundos de sinal.
- O smoke das dependencias privadas passou; a verificacao de ausencia de dados
  do smoke generico falhou por ser incompatível com a edicao pessoal, que inclui
  config, banco e logs por projeto. Nao indica defeito dos runtimes.
- A pasta antiga existia na raiz na ultima inspecao. O usuario autorizou
  elimina-la quando o SSD estiver acessivel. A copia anterior esta em
  `recovery/ssd-root-archive-20261020/`, ignorada pelo Git.
- Naquela inspecao, a copia de desenvolvimento usava a porta 8080 e o mesmo
  ID MQTT. A identidade do laboratorio ja foi separada neste ciclo.
- O APK `2.6.0+12` no SSD tem o mesmo SHA-256 do build release recompilado da
  fonte Flutter atual (`A986EC82AE37C10B9352B80684F0E3C5B27C213157E7BA953E285204498BA0C7`).
  Os 36 testes Flutter passaram; o APK 2.5 da raiz do repositorio e legado.
- A suite Python completa anterior da edicao pessoal passou com 491 testes.
  NotebookLM ainda pede login interativo; uso real no outro PC e celular segue
  sem aceite. Detalhes em `docs/TESTES.md` e `docs/GUIA_SSD_PORTATIL.md`.

## Pendencias dependentes do usuario

1. Conferir as linhas do log do envio no outro PC para fechar a causa exata;
   autenticar WhatsApp em CONFIG no proprio PC se a sessao estiver ausente.
2. Provar no destino com recebimento real nos numeros escolhidos, NotebookLM
   real, mapa mental e desligamento depois de uma tarefa real. Esses testes
   podem ter efeitos externos; no laboratorio so houve verificacao de sessao.
3. O SSD permanece no outro PC. Ao voltar a ficar acessivel, conferir e eliminar
   as pastas antigas autorizadas, preservando a pasta pessoal; validar os dois
   celulares e o inicio no logon. Nao declarar essa limpeza concluida daqui.
4. Goldens Flutter e artefatos de APK/pacote/instalador/atualizador aguardam
   pedido expresso do usuario. Nao iniciar build por iniciativa propria.
