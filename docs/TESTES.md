# Atualização do APK — 24/10/2026

O APK pessoal `2.9.2` (`versionCode` 17) está em
`dist-pacote-pessoal/Controle Android.apk`, com SHA-256
`261E2400B0E7BF93285DF2D9BB0E295D6121196C09464AA496CA68172DF3E959`.
O pacote foi verificado com `aapt` e `apksigner`; a assinatura usa a mesma chave
do projeto. Os textos do menu **Conta NotebookLM** e dos dois comandos estão
presentes nas três arquiteturas do APK. Passaram **45 testes Flutter**, e
`flutter analyze --no-pub` terminou sem problemas. O instalador Windows não
foi alterado. O APK novo e seu `.sha256` foram copiados para a mídia `E:\` e o
hash foi conferido no destino. O APK `2.9.1` anterior foi preservado lá para
reversão. Não havia celular conectado ao ADB, então a instalação no aparelho
não foi conferida nesta sessão.

O menu do NotebookLM agora aparece mesmo sem estado recebido do PC. A
verificação e a tentativa de renovação ocorrem no PC; como não há token durável
do NotebookLM nesta instalação, um login expirado ainda exigirá concluir a
entrada Google no navegador do PC. A interface do celular ainda não foi
conferida no aparelho físico.

# Entrega verificada — 23/10/2026 (histórico)

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
