# Pregacao Controle (Flutter)

App de **controle remoto** do gravador de pregacao (`pregacao-recorder`).
Versao atual **2.0** (Flutter) - substitui o app Kotlin v1.x
(`../../android/`), falando o **mesmo protocolo MQTT/TLS** descrito em
`docs/AGENTE.md`.

O celular e apenas um observador com botoes: mostra o estado do
equipamento e envia `START`/`STOP` (+ Wi-Fi, armazenamento e Drive do
Raspberry). **Audio nunca trafega por aqui.**

## Telas

App **focado no PC da igreja** (captacao local, contas ja logadas no PC):
so a tela de controle e as Configuracoes. As telas de Wi-Fi, armazenamento
e Google Drive do app Kotlin (adaptacoes do Raspberry) foram removidas de
proposito - o PC grava em pasta local e o Drive ja esta logado na maquina.

| Tela | O que faz |
|---|---|
| Principal | `ONLINE/OFFLINE`, estado, cronometro, INICIAR/ENCERRAR, fila de upload, arquivo, eventos |
| Configuracoes | host, porta, TLS, ID do aparelho, usuario `operador`, **token** (gravado no Keystore/Keychain) |

## Compilar

Requisitos: Flutter SDK (stable), Android SDK (platform 36 + build-tools 36),
JDK 17+. O app ja vem com `minSdk 26`, mesmo `applicationId`
(`org.pregacao.controle`) e sequencia de versao do app Kotlin: instalar o
APK novo por cima substitui o antigo (se pedir, desinstale o antigo primeiro:
a chave de assinatura e outra).

```bash
flutter pub get
flutter build apk --release
# saida: build/app/outputs/flutter-apk/app-release.apk (assinado com a
# chave de debug - para distribuir, gere chave propria)
```

iOS: a pasta `ios/` ja esta gerada; `flutter build ipa` num Mac com Xcode
(icone, nome e bundle id ja apontam para `org.pregacao.controle`).

## Testes

```bash
flutter test        # protocolo: comandos, ack, TTL, estados, config
flutter analyze     # zero issues
```

Os testes cobrem a camada Dart pura (`lib/protocolo.dart`,
`lib/configuracao.dart`) - o contrato exato que o agente do Raspberry
espera (`req_id` + `ts` com prazo de validade, payloads de `state`/`ack`).

## Configuracao do operador (uma vez)

1. Abrir o app pela primeira vez: a tela ja orienta.
2. Menu -> **Configuracoes**: host, porta e ID vem **de fabrica** (nao sao
   segredos - estao no painel do equipamento); **so digite o token**
   (cartao CONTROLE REMOTO do painel) e toque em **SALVAR E CONECTAR**.
3. Pronto: o app reconecta sozinho quando a rede volta.

O token e credencial: fica no armazenamento protegido do aparelho
(Keystore/Keychain), nunca no codigo do APK. Para revogar todos os celulares
de uma vez, troque a senha do usuario `operador` no broker
(`docs/EMQX.md`, secao 4).

## Estrutura

```
lib/
├── protocolo.dart         # contrato MQTT (puro Dart, testado)
├── configuracao.dart      # config + armazenamento protegido do token
├── mqtt_controlador.dart  # conexao TLS, auto-reconnect, comandos/ack
├── main.dart              # app + AppScope (controlador unico)
├── tela_principal.dart    # tela de controle
└── tela_configuracoes.dart
test/
├── protocolo_test.dart    # contrato com o agente
└── tela_preview_test.dart # capturas das telas (goldens)
```
