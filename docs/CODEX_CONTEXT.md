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

- O SSD USB `E:` mostra apenas `PregacaoRecorder-Pessoal` como pasta de usuario
  na raiz; `$RECYCLE.BIN` e `System Volume Information` sao do Windows.
- A instalacao pessoal preserva configuracao, contas, historico, 12 gravacoes,
  12 uploads, 2 estudos e o APK. O banco passou em `integrity_check`.
- A instalacao antiga tinha banco vazio e nenhum audio exclusivo: seus nove MP3
  tambem existem na pasta pessoal com o mesmo SHA-256. Ela e os arquivos soltos
  da raiz foram movidos para `recovery/ssd-root-archive-20261020/`, ignorado
  pelo Git. O instalador privado identico permanece em `dist-pacote/`.
- Os 7.859 arquivos publicos da instalacao pessoal passaram na verificacao
  SHA-256. `Verificar Pacote.cmd` passou antes e depois da limpeza sem iniciar
  servicos, captura ou envio. Nao havia servico/tarefa agendada da pasta antiga.
- O APK `2.6.0+12` no SSD tem o mesmo SHA-256 do build release recompilado da
  fonte Flutter atual (`A986EC82AE37C10B9352B80684F0E3C5B27C213157E7BA953E285204498BA0C7`).
  Os 36 testes Flutter passaram; o APK 2.5 da raiz do repositorio e legado.
- A suite Python completa anterior da edicao pessoal passou com 491 testes.
  NotebookLM ainda pede login interativo; uso real no outro PC e celular segue
  sem aceite. Detalhes em `docs/TESTES.md` e `docs/GUIA_SSD_PORTATIL.md`.

## Pendencias e proximo passo

1. Levar o SSD ao PC destino, abrir `PregacaoRecorder-Pessoal/Iniciar Pregacao.cmd` e seguir `docs/ACEITE_WINDOWS.md`.
2. Selecionar audio/disco, autorizar contas/destinatario, definir coexistencia/substituicao e configurar credencial/ACL MQTT/celular; concluir aceite 2.2/2.3.
3. Validar Windows limpo, MP3 real/offline, Drive, NotebookLM/PDF, WhatsApp e STATUS/ACK; registrar resultados antes de declarar entrega pronta.

- Nenhum servidor de desenvolvimento, conta/broker, fila/job ou dado real foi modificado nesta etapa.
- APK Flutter2.6.0+12 reutilizado; sem assistente novo, migrador, atualizador, CI ou recursos Flutter.
- Demais C/D/G03 da auditoria nao corrigidos; conferir servidor/logins/jobs antes de operacao real.
