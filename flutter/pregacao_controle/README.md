# Pregacao Controle

Aplicativo Flutter Android (estrutura tambem para iOS) para controlar o gravador
Windows por MQTT/TLS. O PC grava e processa; o celular exibe estado/progresso.

Fontes: `lib/protocolo.dart`, `mqtt_controlador.dart`, `tela_principal.dart` e
`tela_configuracoes.dart`. O build pessoal gerado por
`packaging/build_connected_release.py` recebe broker, device ID e token do
operador da mesma configuracao usada no instalador Windows. O build publico
continua exigindo configuracao manual. Nenhum comando configura a rede do computador.

Na pasta do app: `flutter test` e `flutter build apk --release`.
Versionamento em `pubspec.yaml`. Alterar fontes nao atualiza APKs instalados.
O modelo `Pregacao` ainda nao tem formulario/CRUD integrado nesta interface.
