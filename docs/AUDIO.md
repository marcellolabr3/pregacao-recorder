# Interface de audio USB

Como configurar, verificar e depurar a captura de audio no Raspberry.

---

## 1. Conexão fisica

```
Soundcraft (MAIN L-R / MIX OUT)   ──RCA/P10──►  Interface USB  ──USB──►  Raspberry Pi 3 B+
```

Recomendacoes:

* use a saida **MAIN L-R** ou **MIX OUT** da mesa, nao o fone de ouvido;
* prefira a porta USB traseira do Raspberry (alimentacao mais estavel);
* evita hubs; se precisar, use hub com alimentacao externa;
* mantenha cabecalhos curtos e blindados;
* o volume de gravacao deve ser ajustado **na mesa**, nao no Raspberry.

---

## 2. Reconhecimento pelo Linux

```bash
arecord -l
```

Saida esperada:

```
**** LISTANDO HARDWARE DE CAPTURA ****
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

```bash
cat /proc/asound/cards
lsusb
dmesg | grep -i audio | tail
```

Se `arecord -l` nao listar nada:

1. troque o cabo USB;
2. teste em outra porta;
3. `sudo apt install --reinstall alsa-utils`;
4. verifique `dmesg` apos reconectar.

---

## 3. O sistema nao usa nome fixo

Por padrao `audio.device = "auto"`:

1. le `arecord -l`;
2. escolhe a **primeira placa USB**;
3. se nao houver USB, usa a primeira placa disponivel;
4. se nao houver nenhuma, recusa iniciar a gravacao com mensagem clara.

Para fixar, escolha na interface (**CONFIG -> Dispositivo de captura**) ou use:

```json
{ "audio": { "device": "plughw:1,0" } }
```

| Valor | Comportamento |
|---|---|
| `auto` | deteccao automatica (recomendado) |
| `hw:1,0` | acesso direto; falha se a taxa for incompativel |
| `plughw:1,0` | com conversao ALSA; mais tolerante |
| `default` | dispositivo padrao do ALSA |

Um dispositivo inexistente e rejeitado pela interface (HTTP 422).

---

## 4. Provar que o Raspberry esta recebendo audio

### Pela interface

**CONFIG -> TESTAR SINAL** captura 2 segundos e mostra o pico em dBFS:

* `pico < -60 dBFS` ou `SILENCIO` -> nada esta chegando;
* `-30 a -6 dBFS` -> sinal saudavel;
* `0 dBFS` -> estourando; abaixe o fader da mesa.

### Pela linha de comando

```bash
pregacao check
```

ou diretamente:

```bash
./scripts/check_audio.sh 3
```

Interpretacao:

```
amostras: 132300  pico: 12450  rms: 2100  pico: -8.4 dBFS
OK: sinal de audio presente.
```

```
SILENCIO: ha captura, mas nenhum sinal chega da mesa.
  -> suba o fader do canal / verifique MAIN L-R / cabecalho USB
```

### Teste "ao vivo" durante uma gravacao

```bash
# durante a gravacao, veja o tamanho dos segmentos crescendo
watch -n2 'ls -l /mnt/ssd/pregacoes/.sessions/*/'

# ou o total capturado
pregacao status
```

Se os segmentos crescem, o audio esta sendo capturado e gravado.

---

## 5. Ajuste de nivel na mesa

1. deixe o fader do canal no posicao habitual da pregação;
2. ajuste o **MAIN** para que os LEDs de pico cheguem ao verde;
3. evite vermelho (clip);
4. se a interface tiver gain proprio, ajuste antes de mexer na mesa.

---

## 6. Formato e qualidade

Padrao (ajustavel em **CONFIG**):

| Parametro | Valor | Motivo |
|---|---|---|
| Formato | `S16_LE` | 16 bits bastam para voz |
| Sample rate | `44100` | universalmente compativel |
| Canais | `2` | preserva L-R |
| Encoder | `mp3` | compativel com o NotebookLM |
| Bitrate | `128 kbps` | ~57 MB/hora, otimo para voz |

Tabela de tamanho:

| Bitrate | 1 hora | 2 horas |
|---|---|---|
| 64 kbps | 28 MB | 57 MB |
| 128 kbps | 57 MB | 115 MB |
| 192 kbps | 86 MB | 173 MB |

Se o `ffmpeg` nao estiver instalado, o sistema grava **WAV** e avisa na tela de
configuracao. WAV e sempre reproduzivel e o NotebookLM aceita, mas ocupa ~317 MB/hora.

---

## 7. Varias interfaces USB conectadas

O `arecord -l` numera em ordem de deteccao, o que pode mudar entre reinicios.

Solucoes:

1. **recomendada** - deixe apenas a interface de gravacao conectada e use `auto`;
2. fixe `hw:X,0` na interface web (a numeracao da placa USB costuma ser
   estavel enquanto o cabecalho nao mudar de porta);
3. udev: `sudo ./scripts/setup_audio_usb.sh` cria
   `/etc/udev/rules.d/99-pregacao-audio.rules`.

---

## 8. Erros comuns

| Mensagem no log | Causa | Solucao |
|---|---|---|
| `arecord nao encontrado` | alsa-utils ausente | `sudo apt install alsa-utils` |
| `nenhuma interface de audio encontrada` | USB desconectado | cabecalho, porta, `lsusb` |
| `Device or resource busy` | outro processo usando o device | `fuser -v /dev/snd/*` |
| `capture_gap: ...` | USB caiu durante a gravacao | cabo/hub; o sistema reconecta sozinho |
| `Invalid sample format` | formato nao suportado | usar `plughw:X,0` |
| `Permission denied` em `/dev/snd` | usuario fora do grupo `audio` | `sudo usermod -aG audio pi` |

---

## 9. Checagem rapida pos-instalacao

```bash
pregacao doctor        # sound, alsa, ffmpeg, drive, pin, servico
pregacao check         # sinal de audio real
pregacao status        # estado geral
```
