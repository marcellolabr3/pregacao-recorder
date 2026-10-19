# Retirada do Raspberry - plano de execucao

Autorizado em 19/10/2026: retirar a parte Raspberry e executar em poucas sprints.
Plataforma do produto: Windows. Preservar gravacao, recuperacao, Drive, estudos,
MQTT/Flutter, credenciais, banco e arquivos locais.

## Sprint 1 - painel e controle remoto

- [x] Remover Ethernet/Wi-Fi/AP/Tailscale e suas chamadas na interface.
- [x] Remover rotas de administracao de rede e comandos MQTT de Wi-Fi.
- [x] Manter indicador de internet usado pelo Drive e pelo controle remoto.
- [x] Corrigir formularios aninhados que interrompem o boot do painel.
- [x] Retirar Wi-Fi da fonte Kotlin legada, sem apagar outros recursos do app.
- [x] Validar APIs, protocolo MQTT e interface com navegador isolado.

Arquivos: `web/`, `app/api/`, `app/remote/agent.py`, `android/`, testes.
Risco: listeners de elementos removidos interromperem o JS; contratos usados
pelo Flutter e historico devem continuar funcionando.

## Sprint 2 - funcionamento no Windows

- [x] Substituir descoberta de montagens Linux por discos/pastas do Windows.
- [x] Preservar destino configurado e recusar destino ausente sem fallback.
- [x] Usar FFmpeg/DirectShow, sem backend ALSA/arecord.
- [x] Usar a pasta do projeto como home padrao, mantendo PREGACAO_HOME.
- [x] Adaptar CLI e estado do agente sem systemctl/sudo.
- [x] Ignorar configuracoes antigas de AP sem apagar a configuracao local.
- [x] Validar armazenamento, captura, caminhos e CLI em ambiente isolado.

Arquivos: `app/storage/`, `app/audio/`, `app/paths.py`, `app/config.py`,
`app/cli.py`, `app/api/routes.py`, testes.
Risco: alterar destino dos dados existentes ou aceitar disco desconectado.

## Sprint 3 - limpeza, documentacao e regressao

- [x] Remover servicos systemd, polkit/sudoers/Avahi e instaladores Linux.
- [x] Atualizar exemplos, manuais e contexto operacional para Windows.
- [x] Atualizar auditoria por IDs sem declarar resolvidas pendencias externas.
- [x] Executar suite Python, verificacao JS e teste de navegador.
- [x] Conferir diff e ausencia de referencias operacionais Linux/Raspberry.

Nao inclui concluir metadados no pipeline, retentativa de WhatsApp ou demais
pendencias independentes da auditoria. Nao publicar, enviar mensagens, renovar
logins ou modificar o pipeline externo. Provas com hardware continuam separadas.

## Estado de entrega

Implementacao e validacao das tres sprints concluidas. O servidor atualizado ja
foi iniciado e as rotas `/api/integracoes`, `/api/pregacoes` e
`/api/importacao/modelo` retornaram 200. Antes do reinicio foram conferidos ausencia
de captura, uploads, estudos e login em execucao; dois estudos em espera preservados.

Depois da retirada, a inicializacao foi consolidada em `iniciar-tudo.bat` e o login
NotebookLM passou a ser monitorado. Estado atual e pendencias em
`docs/CODEX_CONTEXT.md`; verificacao completa atual: 309 testes em `docs/TESTES.md`.

## Resultados e limites

- **268 testes Python passaram em 14,55 s** na etapa de retirada, em copia isolada; a suite atual tem 309 testes verdes (ver `docs/TESTES.md`).
- Testes da plataforma excluida foram substituidos por casos Windows; nao se trata
  da mesma suite de 342 testes registrada na auditoria original.
- Chromium com APIs simuladas: boot, CONFIG, avancadas, cadastro e salvar avancadas
  passaram, com zero erros JS e zero chamadas de administracao de rede.
- Navegador real: card de rede ausente, formulario preservado, zero erros JS.
- `node --check`, parse Python, XML Android e `git diff --check` passaram.
- Descoberta real dos volumes C:/D: e ajuda das CLIs conferidas sem escrita nos discos.
- PDF explicativo regenerado a partir do manual Windows.
- `.env`, tokens OAuth, banco e gravacoes nao foram editados. Contexto antigo com
  notas sensiveis foi preservado em `docs/CODEX_CONTEXT.local.md`, ignorado pelo Git;
  `CONTEXTO.md` passou a apontar para o bootstrap atual, sem segredos.
- Nao houve nova captura, upload, envio WhatsApp, comando MQTT ou login.
- Nao foram executados build/testes Flutter nem build Kotlin; APKs instalados
  permanecem como estavam. A fonte Kotlin perdeu apenas a gestao de rede e textos antigos.
- Outras pendencias C/D continuam abertas. A consolidacao posterior substituiu os consoles minimizados pelo iniciador unico, com os servicos ocultos; ver `docs/WINDOWS.md`.

## Arquivos criados, alterados e removidos

Inventario desta entrega; `M` = alterado, `D` = removido, `N` = novo.
O conteudo dos arquivos locais ignorados nao aparece no diff.

- `N` `.env.example`
- `N` `.gitattributes`
- `M` `.gitignore`
- `M` `CHECKLIST.md`
- `N` `CONTEXTO_AUDITORIA_PRODUTO.md`
- `M` `DOCUMENTACAO.md`
- `M` `GUIA-USUARIO.md`
- `D` `INSTALACAO-RASPBERRY.md`
- `M` `README.md`
- `M` `android/app/build.gradle.kts`
- `M` `android/app/src/main/AndroidManifest.xml`
- `M` `android/app/src/main/java/org/pregacao/controle/DriveActivity.kt`
- `M` `android/app/src/main/java/org/pregacao/controle/MainActivity.kt`
- `M` `android/app/src/main/java/org/pregacao/controle/MqttController.kt`
- `M` `android/app/src/main/java/org/pregacao/controle/StorageActivity.kt`
- `D` `android/app/src/main/java/org/pregacao/controle/WifiActivity.kt`
- `M` `android/app/src/main/res/layout/activity_main.xml`
- `M` `android/app/src/main/res/layout/activity_storage.xml`
- `D` `android/app/src/main/res/layout/activity_wifi.xml`
- `M` `android/app/src/main/res/menu/main.xml`
- `M` `android/app/src/main/res/values/strings.xml`
- `D` `app/api/network_routes.py`
- `M` `app/api/routes.py`
- `M` `app/audio/device.py`
- `M` `app/audio/recorder.py`
- `M` `app/cli.py`
- `M` `app/config.py`
- `M` `app/events.py`
- `M` `app/main.py`
- `M` `app/network/__init__.py`
- `D` `app/network/nm.py`
- `D` `app/network/status.py`
- `D` `app/network/tailscale.py`
- `D` `app/network/watchdog.py`
- `M` `app/paths.py`
- `M` `app/recording/manager.py`
- `M` `app/remote/agent.py`
- `M` `app/storage/destinos.py`
- `M` `app/upload/drive.py`
- `M` `docs/AGENTE.md`
- `M` `docs/AUDIO.md`
- `N` `docs/CODEX_CONTEXT.md`
- `M` `docs/CONFIGURACAO.md`
- `M` `docs/EMQX.md`
- `M` `docs/GOOGLE_DRIVE.md`
- `M` `docs/INSTALACAO.md`
- `M` `docs/PREGACAO-COMO-FUNCIONA.md`
- `M` `docs/PREGACAO-COMO-FUNCIONA.pdf`
- `M` `docs/RECUPERACAO.md`
- `M` `docs/REDE.md`
- `N` `docs/REMOCAO_RASPBERRY.md`
- `M` `docs/SPRINTS.md`
- `M` `docs/TESTES.md`
- `M` `docs/WINDOWS.md`
- `M` `flutter/pregacao_controle/README.md`
- `M` `flutter/pregacao_controle/lib/protocolo.dart`
- `M` `flutter/pregacao_controle/pubspec.yaml`
- `D` `install.sh`
- `D` `scripts/check_audio.sh`
- `D` `scripts/devtools/bin/arecord.exe`
- `D` `scripts/devtools/build_fake_arecord.ps1`
- `D` `scripts/devtools/e2e_test.py`
- `D` `scripts/devtools/fake_arecord.cs`
- `M` `scripts/emqx_check.py`
- `D` `scripts/install.sh`
- `D` `scripts/power_loss_test.sh`
- `D` `scripts/pregacao`
- `N` `scripts/pregacao.cmd`
- `D` `scripts/setup_audio_usb.sh`
- `M` `scripts/smoke.py`
- `D` `scripts/uninstall.sh`
- `D` `scripts/update.sh`
- `D` `system/50-pregacao-network.rules`
- `D` `system/avahi-pregacao-http.service`
- `D` `system/sudoers-pregacao-network`
- `D` `systemd/pregacao-netwatch.service`
- `D` `systemd/pregacao-recorder.service`
- `D` `systemd/pregacao-remote.service`
- `M` `tests/test_api.py`
- `M` `tests/test_audio.py`
- `M` `tests/test_destinos.py`
- `M` `tests/test_manager.py`
- `D` `tests/test_network.py`
- `D` `tests/test_network_api.py`
- `M` `tests/test_recorder.py`
- `M` `tests/test_remote_agent.py`
- `M` `tests/test_silencio.py`
- `N` `tests/test_windows_product.py`
- `D` `uninstall.sh`
- `D` `update.sh`
- `M` `web/static/app.js`
- `M` `web/static/style.css`
- `M` `web/templates/index.html`

Locais ignorados: `CONTEXTO.md` (substituido por ponteiro) e `docs/CODEX_CONTEXT.local.md` (notas legadas preservadas).
