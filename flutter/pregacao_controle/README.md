# Pregacao Controle

Aplicativo Flutter Android (estrutura tambem para iOS) para controlar o gravador
Windows por MQTT/TLS. O PC grava e processa; o celular exibe estado/progresso.

Fontes: `lib/protocolo.dart`, `mqtt_controlador.dart`, `tela_principal.dart`,
`tela_notebooklm.dart` e `tela_configuracoes.dart`. O build pessoal gerado por
`packaging/build_connected_release.py` recebe broker, device ID e token do
operador da mesma configuracao usada no instalador Windows. O build publico
continua exigindo configuracao manual. Nenhum comando configura a rede do computador.

No APK pessoal `2.9.3`, os controles do NotebookLM aparecem somente em
**Configuracoes**, mesmo antes de o PC enviar seu estado. Os comandos ficam
disponiveis quando o PC esta conectado e o estudo automatico esta ativo.
A verificacao e a renovacao automatica, quando houver token duravel, acontecem
no PC. O login Google interativo abre no navegador do PC.

A edicao pessoal fixa host, porta, TLS, ID, usuario e token MQTT recebidos no
build. Ao atualizar de uma versao anterior, ela ignora a conexao antiga salva
no celular e preserva apenas icone e fundo. Salvar a aparencia nao reinicia a
conexao MQTT. A edicao publica continua com configuracao manual.

Na pasta do app: `flutter test` e `flutter build apk --release`.
Versionamento em `pubspec.yaml`. Alterar fontes nao atualiza APKs instalados.
O modelo `Pregacao` ainda nao tem formulario/CRUD integrado nesta interface.
