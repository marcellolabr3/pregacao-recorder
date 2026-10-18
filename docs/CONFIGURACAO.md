# Configuracao

Tudo e configuravel pela interface web - **nenhuma edicao de codigo e necessaria**.

Acesse `http://<ip-do-pi>:8080` -> botao **CONFIG** (canto superior direito).

---

## Onde cada coisa e gravada

| Onde | Arquivo | Conteudo |
|---|---|---|
| Padroes de fabrica | `config/default.json` | versionado no Git |
| Alteracoes da interface | `config/config.json` | gerado, fora do Git |
| Segredos | `.env` | PIN, secret, porta, credenciais |
| Credenciais Google | `config/google_credentials.json` | fora do Git |
| Token Google | `config/google_token.json` | fora do Git, permissao 600 |

---

## EQUIPAMENTO

**Nome do equipamento** - aparece no topo da interface e nos logs.
Ex.: `Pulpito`, `Mesa-Soundcraft`.

---

## AUDIO

| Campo | Padrao | Observacoes |
|---|---|---|
| Dispositivo de captura | `AUTO` | detecta a placa USB automaticamente |
| Formato | `S16_LE` | suficiente para voz; 16 bits |
| Sample rate | `44100` | compativel com a maioria das mesas |
| Canais | `2` | estereo MAIN L-R |
| Encoder final | `mp3` | requer `ffmpeg`; senao grava `wav` |
| Bitrate | `128` | ~57 MB por hora - ideal para voz |
| Tamanho do segmento | `60` s | menor = menos perda em queda de energia |

### Dispositivo explicito

Se quiser fixar, escolha na lista (ex.: `hw:1,0`) ou use `audio.device`:

* `hw:1,0` - acesso direto (sem conversao; falha se taxa incompativel)
* `plughw:1,0` - com conversao ALSA (mais tolerante) - recomendado em duvida

A interface lista as placas reais detectadas; um valor inexistente e rejeitado
com erro `422`.

### Por que gravar em segmentos?

O `arecord` roda continuamente e o processo Python quebra o fluxo em arquivos
WAV de `segment_seconds`. Se a energia cair, apenas o ultimo segmento fica
incompleto - os demais estao integros. O usuario nunca ve os segmentos: a
interface mostra **uma unica gravacao**.

---

## ARMAZENAMENTO

| Campo | Padrao | Observacoes |
|---|---|---|
| Pasta de gravacoes | `recordings/` (vazio = padrao) | use `/mnt/ssd/pregacoes` |
| Espaco minimo (MB) | `512` | abaixo disso, nao inicia gravacao |
| Retencao local (dias) | `0` | `0` = manter para sempre |

Estrutura gerada automaticamente:

```
/mnt/ssd/pregacoes/
├── .sessions/
│   ├── 2026-09-29_130000-a1b2c3/
│   │   ├── session.json
│   │   ├── segment_0001.wav
│   │   └── segment_0002.wav
├── 2026/
│   ├── 09/
│   │   ├── 2026-09-29_130000.mp3
│   │   └── 2026-09-29_150000.mp3
│   └── 10/
└── 2027/
```

Nomes usam apenas `[0-9A-Za-z._-]` - sem acentos, espacos ou simbolos.

---

## GOOGLE DRIVE

| Campo | Padrao | Observacoes |
|---|---|---|
| Client ID (OAuth) | vazio | digitado na interface; termina em `.apps.googleusercontent.com` |
| Client Secret | vazio | digitado na interface; nunca e exibido de volta |
| Habilitar integracao | ligado | desliga toda a parte de envio |
| Upload automatico | ligado | envia sozinho ao finalizar |
| Manter copia local | ligado | desligar = apaga o local apos confirmar |
| Pasta de destino | `Pregacoes` | criada automaticamente |

Conexao: **CONECTAR CONTA** -> abre o login do Google na mesma aba e volta
para a interface automaticamente, com aviso de sucesso ou falha. A tela do
Google mostra o **seletor de contas**, permitindo trocar de conta a qualquer
momento (DESCONECTAR -> CONECTAR CONTA).

Prioridade das credenciais: **interface > `google_credentials.json` > `.env`**.

Detalhes em [GOOGLE_DRIVE.md](GOOGLE_DRIVE.md).

---

## Segredos (`.env`)

```bash
sudo nano /opt/pregacao-recorder/.env
sudo systemctl restart pregacao-recorder
```

| Variavel | Obrigatorio | Descricao |
|---|---|---|
| `PREGACAO_PIN` | sim (min. 4 digitos) | PIN da interface |
| `PREGACAO_SECRET` | sim | assinatura do cookie de sessao |
| `PREGACAO_HOST` | nao | padrao `0.0.0.0` |
| `PREGACAO_PORT` | nao | padrao `8080` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | alternativo ao JSON | fallback |
| `GOOGLE_CREDENTIALS_FILE` | nao | caminho do JSON OAuth |
| `GOOGLE_TOKEN_FILE` | nao | caminho do token salvo |

Nunca commite `.env`. O `.gitignore` ja cobre os arquivos sensiveis.

### Alterando o PIN

```bash
sudo sed -i 's/^PREGACAO_PIN=.*/PREGACAO_PIN=5566/' /opt/pregacao-recorder/.env
sudo chmod 600 /opt/pregacao-recorder/.env
sudo systemctl restart pregacao-recorder
```

---

## Seguranca e rede

* exponha o Raspberry **apenas na rede local** - sem port forwarding, sem DMZ;
* nao ha autenticacao por conta: apenas o PIN local;
* operacoes criticas (iniciar, finalizar, recuperar, descartar, configurar)
  exigem PIN; o estado geral e visivel para quem esta na rede;
* se precisar de acesso remoto, use VPN/tailscale, jamais abrindo a porta.
