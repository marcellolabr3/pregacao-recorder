# Pregacao Recorder - contexto operacional

## Inicio

- Projeto: `D:\Dev\pregacao-recorder`; ler este arquivo e `git status --short`.
- Windows x64: Flask/waitress, SQLite, FFmpeg/DirectShow, painel e Flutter/MQTT.
- Desenvolvimento: `iniciar-tudo.bat`, `.venv\Scripts\python.exe`, painel 127.0.0.1:8080.
- Diagnostico somente leitura: `iniciar-tudo.bat --verificar`.
- `.env`, configuracao pessoal, tokens/perfis, banco, logs e gravacoes nunca entram no Git.
- `docs/CODEX_CONTEXT.local.md` contem legado sensivel; nunca imprimir/commitar.

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

## Pacote generico validado (19-20/10/2026)

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

## Edicao pessoal no SSD (20/10/2026)

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
- A pasta antiga ainda existe na raiz. Uma tentativa de exclusao foi bloqueada
  por revisao automatica; aguardar escolha explicita do usuario antes de mover
  ou tentar nova remocao. A copia anterior esta em
  `recovery/ssd-root-archive-20261020/`, ignorada pelo Git.
- A copia de desenvolvimento nesta maquina esta ativa na porta 8080. A abertura
  completa do SSD nessa porta depende de autorizacao para interrompe-la
  temporariamente. Apenas uma copia deve usar o mesmo ID MQTT por vez.
- O APK `2.6.0+12` no SSD tem o mesmo SHA-256 do build release recompilado da
  fonte Flutter atual (`A986EC82AE37C10B9352B80684F0E3C5B27C213157E7BA953E285204498BA0C7`).
  Os 36 testes Flutter passaram; o APK 2.5 da raiz do repositorio e legado.
- A suite Python completa anterior da edicao pessoal passou com 491 testes.
  NotebookLM ainda pede login interativo; uso real no outro PC e celular segue
  sem aceite. Detalhes em `docs/TESTES.md` e `docs/GUIA_SSD_PORTATIL.md`.

## Pendencias e proximo passo

- Novo pedido (20/10/2026): seguir [tasks e sprints](TASKS_SPRINTS_20261020.md),
  commitar cada sprint e gerar APK/instalador apenas apos todas as mudancas.
  Os processos da copia de desenvolvimento foram encerrados neste PC; o log
  do agente tem 761 quedas MQTT `rc=128`, compativeis com disputa do ClientID
  `pregacao-<device_id>`. O SSD `E:` nao esta acessivel neste PC no momento.

1. Aguardar resposta do usuario sobre destino da pasta antiga e interrupcao temporaria da copia de desenvolvimento para testar o inicio completo do SSD.
2. Levar o SSD ao PC destino, abrir `PregacaoRecorder-Pessoal/Iniciar Pregacao.cmd` e seguir `docs/ACEITE_WINDOWS.md`.
3. Selecionar audio/disco, autorizar contas/destinatario, definir coexistencia/substituicao e configurar credencial/ACL MQTT/celular; concluir aceite 2.2/2.3.
4. Validar Windows limpo, MP3 real/offline, Drive, NotebookLM/PDF, WhatsApp e STATUS/ACK; registrar resultados antes de declarar entrega pronta.

- Nenhum servidor de desenvolvimento, conta/broker ou fila/job foi modificado nesta etapa. O banco/config pessoal foi realocado no primeiro inicio do SSD.
- APK Flutter2.6.0+12 reutilizado; sem assistente novo, migrador, atualizador, CI ou recursos Flutter.
- Demais C/D/G03 da auditoria nao corrigidos; conferir servidor/logins/jobs antes de operacao real.
