# Contexto operacional atual

- Projeto: `D:\Dev\pregacao-recorder`. Não criar pastas de trabalho fora de
  `D:\Dev`; os caches de build ficam em `.bundle-cache/` e `.w/` neste projeto.
- Código atual: `app/`, `web/`, `flutter/pregacao_controle/` e `packaging/`.
- A entrega pessoal atual está em `dist-pacote-pessoal/` e na raiz de `E:\`:
  um instalador Windows privado e um APK separado. A cópia de `E:\` foi
  atualizada com o APK `2.9.3` em 24/10; o `2.9.2` ficou como backup. O
  instalador inclui broker MQTT, ID do dispositivo,
  autorização renovável do Google Drive, sessão NotebookLM e sessão WhatsApp
  quando presentes. O APK inclui a conexão MQTT do operador.
- `packaging/build_connected_release.py` monta os dois arquivos pessoais a partir
  das conexões atuais. `packaging/build_release.py` monta a edição pública sem
  credenciais em `dist-pacote/`. Não publicar o instalador pessoal no GitHub.
- Gravação local funciona sem conta Google ativa ou internet. O envio ao Drive
  fica pendente até haver autorização e conexão. No PC novo, reescolher a
  interface de áudio e o destino de gravação. Como o ID MQTT é preservado,
  desligar o agente do PC antigo antes de ativar o novo.
- `.env`, `config/config.json`, `config/google_token.json`, `data/`,
  `recordings/`, `recovery/`, `logs/` e `.signing/` são dados locais e ficam
  fora do Git. Não incluir artefatos pessoais em commits.
- A fonte roda com `.venv\Scripts\python.exe` e `iniciar-tudo.bat`; o
  diagnóstico sem iniciar serviços é `iniciar-tudo.bat --verificar`. Não mover
  `.venv/`, `config/`, `data/`, `recordings/` ou `logs/` enquanto o serviço roda.
- Guias: [instalação pessoal](GUIA_INSTALACAO_CONECTADA.md),
  [instalação pública](GUIA_INSTALACAO_WINDOWS.md),
  [aceite no novo PC](ACEITE_WINDOWS.md) e [testes](TESTES.md).
