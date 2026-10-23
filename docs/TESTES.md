# Verificação atual — 23/10/2026

- `python -B -m pytest`: **537 testes passaram** após arquivar o código legado.
  Uma asserção assíncrona de estudo foi ajustada para esperar o evento real;
  os 28 testes direcionados passaram antes da execução completa.
- `flutter test --no-pub`: **42 testes passaram**.
- `flutter analyze --no-pub`: **nenhum problema**.
- Os arquivos em `E:\Gerador de Estudo\` foram conferidos por SHA-256:
  `Gerador de Estudo.exe` =
  `A1F198B2FC32E500DA4F1EFA05DC6F75CB3F0921EEC071955806AFE231F65382`;
  `Controle Android.apk` =
  `B69814FF70FE6C6A9EA6EBD3E3B79D748010C8E84236ECF82F06215DC89EBAF1`.
  A pasta contém somente esses dois arquivos.
- Após a separação em `.OLD/`, a API local respondeu em estado `IDLE` e os
  processos do gravador e do agente continuaram ativos.

A instalação, captura pela interface de áudio, autorização Google e conexão
MQTT reais ainda precisam ser conferidas no computador de destino, seguindo
[ACEITE_WINDOWS.md](ACEITE_WINDOWS.md). O arquivo histórico de testes desta
máquina está em `.OLD/docs/TESTES-20261021.md` e não vai ao GitHub.
