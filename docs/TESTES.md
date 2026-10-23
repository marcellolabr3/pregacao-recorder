# Entrega verificada — 23/10/2026

Os dois artefatos pessoais estão em `dist-pacote-pessoal/` e foram copiados para
a raiz de `E:\`. Os hashes SHA-256 conferem na origem e no destino:

| Arquivo | SHA-256 |
|---|---|
| `Gerador de Estudo.exe` | `D77E8250EA10B9473FBC2A2CE1A68192EB8B586D63BD9B79930ECDAD800CDEA6` |
| `Controle Android.apk` | `87EC6B9FC9E40D34FBB0328874ABD1DB6D780F7C09995B726EA1B50D2C848B93` |

O APK foi verificado com `apksigner`; a credencial MQTT do operador conectou ao
broker e assinou o tópico de estado. A suíte Python passou com **548 testes**,
a suíte Flutter com **44 testes**, e `flutter analyze --no-pub` terminou sem
problemas. O serviço local foi reiniciado após a limpeza dos logs antigos e
voltou ao estado `IDLE`, sem uploads pendentes.

A sessão NotebookLM incluída no instalador já está expirada e não há token
durável nesta entrega. O botão **RENOVAR LOGIN NO PC** no painel ou no APK abre
o navegador do computador para concluir a entrada na conta Google. Após essa
entrada, gere novamente a entrega se quiser incluir um token durável.

A gravação com a interface de áudio do novo PC e o uso real de Drive,
NotebookLM, WhatsApp e controle Android ainda devem ser conferidos após a
instalação. Use o [roteiro de aceite](ACEITE_WINDOWS.md).
