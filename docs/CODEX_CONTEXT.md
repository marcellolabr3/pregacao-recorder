# Pregacao Recorder - contexto operacional

## Inicio

- Projeto: `D:\Dev\pregacao-recorder`; ler este arquivo e `git status --short`.
- Windows: Flask/waitress, SQLite, FFmpeg/DirectShow, web e Flutter/MQTT.
- Desenvolvimento: `iniciar-tudo.bat`, `.venv\Scripts\python.exe`, painel 127.0.0.1:8080.
- Diagnostico somente leitura: `iniciar-tudo.bat --verificar`.
- `.env`, configuracao pessoal, tokens/perfis, banco, logs e gravacoes nunca entram no Git.
- `docs/CODEX_CONTEXT.local.md` e legado local sensivel; nunca imprimir/commitar.

## Arquitetura e regras

- Gravacao local independe de internet/MQTT; PC processa, celular controla.
- Upload Drive e estudo sao filas independentes; contrato pipeline.py AUDIO --skip-drive [--to NUMERO].
- Desenvolvimento ainda usa pipeline externo configurado; fonte original em
  `C:\Users\Aska\Documents\Default Project\sermon-pipeline` nao foi modificada.
- Pacote usa fontes minimas em `vendor/sermon-pipeline/`, com prompt preservado e SOURCE.json.
- Preservar dados/jobs/credenciais; testar com home e bancos isolados.
- Nao executar `_instalador/ajustar_caminhos.py` nem copiar .venv com remendos.
- Auditoria e limites: `CONTEXTO_AUDITORIA_PRODUTO.md` (IDs A-G).

## Estado implementado da sprint 1 (19/10/2026)

- Implementacao da sprint 1 publicada no GitHub no commit `868cf83`.
- Task pessoal PR-DIST-001 em `docs/TASK_DISTRIBUICAO_WINDOWS.md`; tres sprints, sem recursos novos.
- `packaging/build_bundle.py` monta ZIP com fontes por allowlist e manifesto/hash de 7.575 arquivos.
- Runtime privado: Python embeddable 3.11.9, 63 distribuicoes Python fixadas com hashes,
  Node 24.18.0, FFmpeg/ffprobe e Chromium; nao copia ambientes instalados.
- `app/bundled_runtime.py` prepara caminhos/perfil/config inicial apenas no pacote;
  `app/estudos.py` usa python -m notebooklm e Chromium nesse modo. Dev preservado.
- `.env`, config pessoal, banco, auth/QR/cookies e gravacoes excluidos do pacote.
- ZIP local: `dist-pacote/PregacaoRecorder-sprint1-20261019T142634742522Z.zip` (478,8 MiB); checksum no arquivo `.sha256` ao lado.
- `.bundle-cache/` e `dist-pacote/` ignorados; ZIP/runtimes sao locais, nao enviados ao GitHub.
- Raiz curta do ZIP: PregacaoRecorder/.
- ZIP montado antes do commit; `source_revision=576f1c2-dirty`; integridade rastreada pelos hashes.
- Entrada do ZIP: Iniciar Pregacao.cmd; diagnostico: Verificar Pacote.cmd.
- CMD testado na copia extraida: raiz resolvida antes de mudar diretorio; diagnostico sem escrita.
- Instrucoes de build/uso em `packaging/README.md`; instalador .exe ainda nao criado.
- 350 testes passaram em copia isolada. Smoke local com PATH isolado passou:
  imports, PDF, XLSX, Chromium offline, CLI, Node local, dshow e MP3 sintetico/ffprobe.
- Diagnostico nao cria config/banco/logs. Avisos de contas ainda ausentes sao esperados.
- Correcao MAX_PATH: ZIP com raiz curta; extracao em caminho com espacos/acentos/& e smoke passaram.
- Nao reiniciou servicos em uso nem executou login, captura real, upload ou envio.
- Retirada Raspberry e formularios web corrigidos antes desta sprint; preservar.

## Pendencias e proximo passo

- Aceite em Windows limpo ainda pendente; isolamento/extracao local passaram.
- Proximo passo exato: PR-DIST-001.2.1, criar instalador .exe/atalho em `%LOCALAPPDATA%\PregacaoRecorder`.
- Depois PR-DIST-001.2.2 a 2.5: contas/audio/destino, MQTT e ajustes G01/G02, preservando dados.
- ZIP ainda sem configuracao pessoal/segredo preparado; isso pertence a sprint 2.
- G01: corrida login/pipeline herdada. G02: identidade de PID entre copias. Nao corrigidos na sprint 1.
- Config inicial salva caminhos absolutos; extrair no destino definitivo antes do primeiro uso.
- Sprint 3: Windows limpo e PC destino, audio real, Drive/NotebookLM/PDF/WhatsApp e celular atual.
- APK Flutter 2.6.0+12 reutilizado; Kotlin legado, sem build/assinatura novos nesta tarefa.
- Novos checkpoints, atualizador, CI, migrador e recursos Flutter ficaram fora do escopo.
- Outros achados C/D/G03 permanecem auditados; nao considerar corrigidos por empacotar.
- Estado antigo do servidor/logins/estudos nao foi reconsultado; conferir antes de qualquer operacao.
