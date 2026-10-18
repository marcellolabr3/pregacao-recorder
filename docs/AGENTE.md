# AGENTE - controle remoto (APK Android)

> Documento tecnico do **Remote Agent**, a peca que permite gravar e
> acompanhar a pregacao de qualquer lugar, pelo celular.
> Visao geral do equipamento: `DOCUMENTACAO.md`. Rede: `docs/REDE.md`.
> Aplicativo do celular (fonte e build): **secao 13**.

---

## 1. Resumo em uma frase

O equipamento mantem uma **conexao de saida** para um servico remoto
(MQTT sobre TLS) e o APK, do outro lado da Internet, envia comandos e
recebe o estado - sem port forwarding, sem IP publico, sem mexer no
roteador da igreja.

---

## 2. O que o agente e (e o que ele NAO e)

**E:**

* um processo separado, `pregacao-remote.service`, que so conversa;
* uma ponte: comando chega por MQTT, e executado na **API local**
  (`/api/start`, `/api/stop`, `/api/status`) - a mesma que o painel usa;
* um publicador de estado, eventos e disponibilidade.

**NAO e:**

* nao substitui o gravador: se o agente cair, a gravacao, a recuperacao de
  quedas e o upload continuam normalmente;
* nao passa audio: nenhum byte de som transita pelo servico remoto;
* nao e requisito para gravar: com `PREGACAO_REMOTE_HOST` vazio o agente
  nem sobe (e esse e o padrao de fabrica).

```
APK Android <--Internet--> servico remoto <--MQTT/TLS (saida)--> AGENTE
                                                                      |
                                                                HTTP localhost
                                                                      v
                                                                 RECORDER -> SSD
```

Toda conexao e iniciada **pelo Raspberry** (NAT amigavel).

---

## 3. Topics e mensagens

Tudo sob `pregacao/<device_id>/`, com `device_id` padrao
`pregacao-igreja-01`:

| Topic | Quem publica | Conteudo | Retido? |
|---|---|---|---|
| `.../cmd` | APK | `{"cmd":"START","req_id":"abc"}` | nao |
| `.../ack` | agente | resposta ao `req_id` | nao |
| `.../state` | agente | estado completo do equipamento | **sim** |
| `.../events` | agente | eventos (`gravacao_*`, `upload_*`) | nao |
| `.../avail` | agente/broker | `online` / `offline` | **sim** (LWT) |

* `state` retido: quem conectar ja ve o estado atual, sem esperar evento.
* `avail` com LWT: se o Pi cair sem desligar (queda de energia), o broker
  publica `offline` sozinho.

### 3.1 Payload de `state`

```json
{
  "device_id": "pregacao-igreja-01",
  "device_name": "Smoke",
  "state": "IDLE",
  "banner": "PRONTO",
  "detail": "",
  "session_id": null,
  "started_at": null,
  "recording": {"active": false, "segments": 0, "bytes": 0, "duration": 0.0},
  "uploads": {"pending": 0, "running": 0, "done": 0, "failed": 0},
  "drive_connected": false,
  "network_online": true,
  "api_ok": true,
  "ts": 1790941693.6
}
```

O cronometro **nao** e republicado a cada segundo: o APK calcula a duracao a
partir de `started_at`. `api_ok: false` significa que a API local nao
respondeu (o equipamento pode continuar gravando).

---

## 4. Estados

| Estado | Significado para o operador |
|---|---|
| `OFFLINE` | sem conexao com o equipamento (o `avail` vira `offline`) |
| `ONLINE` | conectado |
| `IDLE` | pronto para gravar |
| `RECORDING` | gravando |
| `STOPPING` | encerrando a gravacao |
| `UPLOAD_PENDING` | arquivo local aguardando envio ao Drive |
| `UPLOADING` | enviando ao Drive |
| `UPLOADED` | enviado com sucesso |
| `ERROR` | algo exige atencao (ver `banner`/`detail`) |

---

## 5. Eventos

O agente consome o fluxo SSE do equipamento (`/api/stream`) e repassa os
eventos para `.../events`, **exceto** `status`, `tick` e `upload_progress`
(estes viram atualizacao de `state` ou sao ignorados para nao poluir).

Kinds relevantes: `gravacao_iniciada`, `gravacao_finalizada`,
`gravacao_pronta`, `gravacao_vazia`, `upload_pendente`, `upload_inicio`,
`upload_concluido`, `upload_falho`, `recuperacao`, `conversao`, `erro`.

Formato:

```json
{"kind": "gravacao_iniciada", "seq": 12, "ts": 1790941693.6, "data": {...}}
```

---

## 6. Comandos e idempotencia

### 6.0 Envelope: req_id e prazo de validade

Todo comando e um JSON em `cmd` (o texto puro `START` tambem funciona):

```json
{"cmd": "START", "req_id": "fl-1790941693-4f2a", "ts": 1790941693.6}
```

* `req_id`: identificador unico do envio - e o que correlaciona o `ack`
  com o botao que apertou (respostas atrasadas de outro pedido sao
  descartadas pelo aplicativo).
* `ts`: epoch (segundos) no momento do envio. E o **prazo de validade**: o
  agente recusa comandos com desvio maior que `COMANDO_TTL_SEGUNDOS` (120 s)
  do relogio local, ANTES de tocar na API local - um comando atrasado (fila
  parada, reenvio tardio) nao pode executar depois que a situacao mudou.
  A recusa vem `ok:false` + `error:"comando expirado..."` + `cmd`/`req_id`.
* Comandos **sem** `ts` (APK Kotlin antigo) continuam aceitos: o prazo e
  progressivo, nao uma quebra de compatibilidade.
* Comandos nunca sao publicados com retencao (`retain:false`).

### 6.1 STATUS

Responde `ok:true` e o resumo do equipamento em `status`.

### 6.2 START

| Situacao | Resposta |
|---|---|
| parado | chama `/api/start`; `ok:true` se gravar, `ok:false` + `error` se recusar |
| ja gravando | `ok:true`, `idempotent:true`, `detail:"ja existe gravacao em andamento"` |

**Nunca** ha uma segunda gravacao: a protecao de verdade continua sendo o
servidor (HTTP 409), o agente apenas responde de forma previsivel.

### 6.3 STOP

| Situacao | Resposta |
|---|---|
| gravando | chama `/api/stop` |
| finalizando | `ok:true`, `idempotent:true`, `detail:"gravacao ja em finalizacao"` |
| parado | `ok:true`, `idempotent:true`, `detail:"nenhuma gravacao em andamento"` |

### 6.4 WIFI_SCAN / WIFI_CONNECT

Le as redes que **o equipamento** enxerga. O celular so pede: quem varre e
quem conecta e o Raspberry, o Wi-Fi do celular nao muda nada (e o APK diz
isso na tela, para o operador nao se confundir).

| Comando | Argumento | Resposta |
|---|---|---|
| `WIFI_SCAN` | — | `ok:true` + `count` + `networks` (`ssid`, `signal`, `strength`, `security`, `secure`, `in_use`) |
| `WIFI_CONNECT` | `ssid` (obrigatorio), `password` (opcional) | `ok:true` + `ssid`; recusa vem `code:"wifi_falhou"` com a propria mensagem do `nmcli` |

`WIFI_CONNECT` sem `ssid` e recusado **no agente**, antes de tocar em rede
nenhuma (`code:"ssid_obrigatorio"`), mas mantendo `cmd` e `req_id` para o
APK saber de qual botao e a resposta.

Sao as unicas rotas remotas que passam por `@require_admin`: por isso o
`LocalApi` do agente recebe tambem o `PREGACAO_ADMIN_PIN` e sobe a sessao de
administrador **so quando o servidor reclamar** (`403 admin_obrigatorio`).
A ordem importa, porque `is_admin()` so vale depois do login comum. Sem esse
PIN o comando chega e volta 403 - e o `admin_login` e feito uma unica vez
por processo, ja que o cookie persiste no cookie jar.

### 6.5 Formato do `ack`

```json
{"cmd":"START","req_id":"abc","ok":true,"ts":1790941695.2,"state":"RECORDING"}
```

Falhas trazem `ok:false` + `error` (mensagem legivel) + `code`
(`estado_invalido`, `sem_resposta`, `erro_interno`, `ssid_obrigatorio`,
`wifi_falhou`, `sem_networkmanager`).

`req_id` vem do APK e volta identico: e o que permite correlacionar
resposta e pedido. Argumentos (`ssid`, `password`) tambem vem do APK e sao
repassados a API local sem alteracao.

---

## 7. Configuracao (`.env`, secao 8)

Segredos **nunca** ficam no codigo - estao em `/opt/pregacao-recorder/.env`
(`chmod 600`), documentados em `.env.example`.

| Variavel | Padrao | Funcao |
|---|---|---|
| `PREGACAO_REMOTE_HOST` | vazio | host do broker; vazio = agente off |
| `PREGACAO_REMOTE_PORT` | `8883` | porta TLS |
| `PREGACAO_REMOTE_TLS` | `1` | obriga TLS |
| `PREGACAO_DEVICE_ID` | machine-id | vira os topics |
| `PREGACAO_REMOTE_USERNAME` | = device_id | usuario do aparelho |
| `PREGACAO_REMOTE_PASSWORD` | vazio | senha do aparelho |
| `PREGACAO_OPERATOR_TOKEN` | vazio | token digitado no APK |
| `PREGACAO_REMOTE_INTERVAL` | `10` | periodo do estado de seguranca (min 2) |
| `PREGACAO_REMOTE_ENABLED` | `auto` | `0` desliga mesmo com host preenchido |

### ACL sugerida no broker

Dois usuarios distintos (o aparelho **nao** reutiliza a senha no celular):

```
usuario "aparelho"  senha = PREGACAO_REMOTE_PASSWORD
    publica em  pregacao/<device_id>/{avail,state,events,ack}
    assina      pregacao/<device_id>/cmd

usuario "operador"  senha = PREGACAO_OPERATOR_TOKEN
    assina      pregacao/<device_id>/{avail,state,events,ack}
    publica em  pregacao/<device_id>/cmd
```

O usuario do aparelho e o proprio `PREGACAO_REMOTE_USERNAME` (padrao: o
`device_id`). O usuario `operador` e fixo: e o que o APK preenche
automaticamente em Configuracoes.

Apos mexer no `.env`:

```bash
sudo systemctl restart pregacao-remote
```

---

## 8. Instalacao e atualizacao

O `install.sh` e o `update.sh` ja cuidam disso:

* copiam `systemd/pregacao-remote.service` para `/etc/systemd/system/`;
* ajustam `User=` e `ExecStart=` para o usuario do servico e o venv
  (`/opt/pregacao-recorder/.venv/bin/python -m app.remote.agent`);
* `systemctl enable` + `restart`.

O unit roda **depois** de `pregacao-recorder.service` (`After=`), com
`Restart=on-failure`, limite de 10 reinicios em 300 s e encerramento limpo
(SIGTERM publica `offline` antes de sair; o LWT cobre queda abrupta).

> Atencao: nao instale o unit com `install -m644` direto. Sem o `sed` do
> `update.sh` ele fica com `User=pi` e `ExecStart=/usr/bin/python3` e o
> systemd responde `217/USER`.

---

## 9. Logs e comandos uteis

```bash
# acompanhar em tempo real
journalctl -u pregacao-remote -f

# arquivo proprio do agente
tail -f /opt/pregacao-recorder/logs/pregacao-remote.log

# estado do servico
systemctl status pregacao-remote
systemctl is-enabled pregacao-remote

# se ficou em "failed" apos muitas tentativas
sudo systemctl reset-failed pregacao-remote && sudo systemctl start pregacao-remote
```

Linhas com tag `[REMOTE]`:

```
[REMOTE] agente iniciando (broker=...:8883 tls=True device_id=pregacao-igreja-01 ...)
[REMOTE] conectado a ... (device_id=pregacao-igreja-01)
[REMOTE] escutando eventos do equipamento
[REMOTE] comando recebido: START
```

Se a API local cair, aparece **uma unica** linha
`fluxo de eventos encerrado`; as repetidas ficam em DEBUG (para o journal
nao encher de linha identica e esconder o problema real).

---

## 10. Testes

```bash
python -m pytest tests/test_remote_agent.py -q
python -m pytest tests -q
```

A suite completa tem **212 testes**, cobrindo topics, parsing de comando
(inclusive os argumentos `ssid`/`password`), idempotencia de START/STOP,
subida de sessao de administrador, `ack`, estado retido, ciclo de vida do
servico e as assinaturas de callback do paho (v1 e v2).

Para validar ao vivo (de qualquer maquina com Internet):

```bash
python scripts/emqx_check.py            # ciclo STATUS/START/START/STOP
python scripts/emqx_check.py STATUS     # so um comando
```

As credenciais sao lidas do `.env` (nunca do codigo).

---

## 11. Solucao de problemas

| Sintoma | Causa provavel | Acao |
|---|---|---|
| `systemctl` diz `217/USER` | unit instalado sem o `sed` do update.sh | rode `bash update.sh` |
| `Start request repeated too quickly` | crash-loop bateu o limite | `reset-failed` + `start` |
| `Unknown key 'StartLimitIntervalSec' in [Service]` | chave no lugar errado | deve estar em `[Unit]` |
| agente em `failed` sem log | `PREGACAO_REMOTE_HOST` vazio (exit 0) | esperado; preencha o host |
| `avail` fica `offline` | Pi sem Internet ou caiu | veja `journalctl -u pregacao-remote` |
| `ack` nunca chega | ACL do broker bloqueando o `cmd` | revise permissoes no painel do provedor |
| `api_ok:false` no state | API local fora do ar | `systemctl status pregacao-recorder` |
| `sem_resposta` no ack | API local nao respondeu em 20 s | veja o log do gravador |
| DeprecationWarning do paho | API de callbacks antiga | atualize a fonte (ja migrado para v2) |

---

## 12. Seguranca

* O agente fala com a API local usando o **PIN de acesso** ja existente -
  nenhuma credencial nova e criada para o equipamento.
* O **token do operador** (`PREGACAO_OPERATOR_TOKEN`) e digitado uma unica
  vez no APK e mostra ao administrador no painel (cartao **CONTROLE
  REMOTO**); nunca aparece para usuario final.
* `device_id` e o unico identificador visivel em `/api/status` (nao exige
  administrador).
* TLS e obrigatorio por padrao (`PREGACAO_REMOTE_TLS=1`).
* Todas as credenciais ficam no `.env` (`chmod 600`), fora do Git e fora
  do pacote de deploy.

---

## 13. O aplicativo (APK Android)

> **App atual: Flutter** (`flutter/pregacao_controle/`). A fonte Kotlin
> original (`android/`) foi o app v1.x (ate a versao 1.4) e permanece como
> referencia; o app entregue aos operadores agora e o Flutter (v2.0+), com
> as mesmas telas e o mesmo protocolo. As secoes 13.1 e 13.2 valem para os
> dois. Build do Flutter: `cd flutter/pregacao_controle && flutter build
> apk --release` (saida em `build/app/outputs/flutter-apk/`); iOS e
> preparado no mesmo projeto (`flutter build ipa` num Mac).

Fonte em `android/` (dentro deste repositorio). A pasta **nao** vai para o
Pi: o APK e construido num computador com o SDK do Android (o mesmo vale
para `flutter/`, ja excluido no `install.sh`/`update.sh`).

### 13.1 O que ele faz (e o que ele NAO faz)

**Faz:** mostra `ONLINE/OFFLINE`, o estado (`PRONTO`, `GRAVANDO`,
`ENCERRANDO`, `ENVIANDO`, `ENVIADO`, `ATENCAO`), o **TEMPO** de gravacao,
o **ARQUIVO** salvo, a fila de upload e os ultimos eventos - e envia
`START`/`STOP`.

**NAO faz:** nao grava som, nao recebe som, nao guarda historico.
O pacote **nao tem a permissao `RECORD_AUDIO`** - o Android a recusaria de
qualquer forma, e e possivel conferir com:

```bash
aapt2 dump badging app-debug.apk | grep uses-permission
```

### 13.2 Configuracao (uma unica vez, no celular)

Menu **Configuracoes**:

| Campo | De onde vem | Padrao |
|---|---|---|
| Servico remoto (host) | painel, cartao CONTROLE REMOTO | `d1901dc1.ala.us-east-1.emqxsl.com` |
| Porta | painel | `8883` |
| Usar TLS | painel | ligado |
| ID do aparelho | painel, cartao CONTROLE REMOTO | `pregacao-igreja-01` |
| Usuario do operador | fixo | `operador` |
| Token do operador | painel (PIN de administrador) | **vazio - precisa digitar** |

Host, porta e ID vem **de fabrica** (`Prefs.PADRAO_SERVIDOR` /
`Prefs.PADRAO_APARELHO` e os `android:text` do layout): nao mudam e nao sao
segredos, entao o operador nao precisa achar nenhum campo escondido - na
pratica ele so digita o **token**, uma unica vez.

O token fica **no celular** (SharedPreferences), nunca no codigo do APK. O
`pronto()` exige token preenchido: sem ele a tela principal mostra a
orientacao em vez de tentar conectar com credencial vazia.

> **Verificado no aparelho (Redmi Note 13):** com a tela original alta, o
> campo "Servico remoto" ficava no topo e sumia quando o teclado empurrava a
> lista para baixo - o operador via so "Falta o servidor". Por isso os
> valores vem prontos e, quando falta campo, a tela **rola sozinha ate ele**
> (`SettingsActivity.rolarPara`).

### 13.3 Como construir

Requisitos: JDK 17, Android SDK (platform 35 + build-tools 35) e Gradle 8.x.

```bash
export JAVA_HOME=/caminho/para/jdk17
export ANDROID_HOME=/caminho/para/Android/Sdk
gradle -p android assembleDebug
```

Saida: `android/app/build/outputs/apk/debug/app-debug.apk` (~0,9 MB,
assinado com a chave de debug - serve para teste; para distribuir, gere uma
chave propria e use `assembleRelease`).

A versao vem de `versionName`/`versionCode` em `android/app/build.gradle.kts`
(hoje **1.2** / **3**) e aparece na barra superior do app. Ao entregar uma
build nova, suba o numero: e' o operador que precisa conferir, sem abrir os
Ajustes do Android, qual versao esta instalada.

### 13.4 Como instalar no celular

1. Copie o `.apk` para o celular (cabo USB, nuvem ou QR).
2. Toque no arquivo. O Android vai pedir para permitir **instalar apps de
   fontes desconhecidas** - permita so para o gerenciador que voce usou.
3. Abra **Pregacao Controle** e va em Configuracoes.
4. Host, ID, porta e usuario ja vem preenchidos - confira e **so digite o
   token**; toque em **SALVAR E CONECTAR**.
5. Confira a versao na barra superior: se nao for a ultima entregue, instale
   de novo o `.apk` novo por cima (mesmo pacote, atualiza em sitio).

### 13.5 Comportamento

* Reconexao automatica: se a Internet do celular cair e voltar, a tela
  volta a atualizar sozinha (o proprio cliente MQTT reconecta).
* A conexao e encerrada quando a tela sai de cena (economia de bateria).
* `ENCERRAR GRAVACAO` sempre pede confirmacao antes de mandar o `STOP`.
* O botao fica desabilitado ate o `ack` chegar (nao da para mandar START
  duas vezes por engano).
* Quem nao configurou nada ve a orientacao na propria tela.

### 13.6 O que esta verificado

App Flutter (2.0, `flutter/pregacao_controle/`):

* `flutter analyze`: **zero issues** (Flutter 3.47.3+);
* `flutter test`: **19 testes de protocolo verdes** (comandos com
  `req_id`+`ts`, correlacao de `ack`, payload de `state`/`events`,
  cronometro, `Configuracao` roundtrip com token);
* build `flutter build apk --release` concluido (RC=0) - verificado por
  busca no `.apk`: nao contem token, senha de broker nem credencial
  (os valores de fabrica sao host/ID publicos, como no app Kotlin);
* mesmo `applicationId` (`org.pregacao.controle`) e sequencia de versao do
  app Kotlin: instalar por cima substitui (mesma assinatura de debug nao
  garante atualizacao em sitio - se o Android recusar por assinatura,
  desinstale o antigo primeiro; **os celulares nao perdem nada**: a
  configuracao e so o token, digitado de novo);
* `minSdk 26`, so `INTERNET` e `ACCESS_NETWORK_STATE`;
* **pendente**: instalacao em celular real e ciclo completo ao vivo
  (os mesmos passos da secao "Como testar o controle remoto (APK) de
  verdade" do `CHECKLIST.md`).

App Kotlin 1.x (`android/`, referencia legada):

* compila sem nenhum aviso do compilador (`gradle assembleDebug`, RC=0);
* **Android Lint: 0 erros e 0 avisos** (`gradle lintDebug`);
* manifesto: `minSdk 26`, `targetSdk 35`, so `INTERNET` e
  `ACCESS_NETWORK_STATE`, `usesCleartextTraffic=false`;
* o rotulo do botao acompanha o estado (`INICIAR GRAVACAO` parado,
  `ENCERRAR GRAVACAO` gravando, `AGUARDE...` encerrando) - sem isso ele
  mostraria "INICIAR GRAVACAO" com a gravacao ja rolando;
* o pacote **nao** contem PINs, senha do broker, `device_id` nem
  variaveis `PREGACAO_*` (verificado por busca no `.apk`);
* **pendente**: instalacao em celular real e ciclo completo ao vivo
  (`START` gravando de verdade, `ENCERRAR` com confirmacao, queda de
  Internet durante a gravacao) - esta no `CHECKLIST.md`, secao
  "Controle remoto (APK)".
