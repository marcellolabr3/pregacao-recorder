# Instalacao

Guia completo para instalar o **pregacao-recorder** em um Raspberry Pi 3 Model B+.

---

## 1. Requisitos

| Item | Observacao |
|---|---|
| Raspberry Pi 3 Model B+ | sem monitor, teclado ou mouse |
| MicroSD 16 GB+ | apenas para o sistema e a aplicacao |
| SSD/HD USB | armazenamento permanente das gravacoes |
| Interface de audio USB | reconhecida pelo ALSA (ex.: Behringer UCA222, Focusrite Scarlett Solo) |
| Roteador local | o celular acessa pela rede da igreja |
| Cabeamento P10/XLR | saida MAIN L-R da mesa Soundcraft -> entrada da interface |

Nao e necessario desktop grafico.

---

## 1.1 Sistema operacional

1. Baixe **Raspberry Pi OS Lite 64-bit** (sem desktop).
2. Grave a imagem no microSD com o Raspberry Pi Imager.
3. Antes de bootar, configure via Imager:
   * nome de host: `pregacao`
   * usuario: `pi`
   * habilitar **SSH** (chave ou senha)
   * configurar **WiFi** e local (opcional mas util)
4. Conecte o SSD USB e, se possivel, configure o montagem automatica
   (veja [3. Armazenamento](#3-armazenamento-ssd)).

---

## 2. Instalacao

```bash
ssh pi@pregacao   # ou pi@<ip>

# dependencias minimas para clonar
sudo apt update && sudo apt install -y git

git clone <url-do-repositorio> /home/pi/pregacao-recorder
cd /home/pi/pregacao-recorder

sudo bash ./scripts/install.sh
```

O script:

1. instala `python3`, `alsa-utils`, `ffmpeg`, `usbutils`;
2. copia o projeto para `/opt/pregacao-recorder`;
3. cria um virtualenv com as dependencias;
4. gera `/opt/pregacao-recorder/.env` com **PIN aleatorio** e secret;
5. instala e habilita o servico `pregacao-recorder.service`;
6. cria o comando `pregacao`.

> **Anote o PIN exibido no final da instalacao** - ele esta em
> `/opt/pregacao-recorder/.env` (`PREGACAO_PIN`).

---

## 3. Armazenamento (SSD)

As gravacoes **nao** devem ficar no microSD.

### Opcao A - pasta no SSD ja montado

Se o SSD ja monta em `/mnt/ssd`:

```bash
sudo mkdir -p /mnt/ssd/pregacoes
sudo chown -R pi:pi /mnt/ssd/pregacoes
```

Depois, na interface: **CONFIG -> Armazenamento -> Pasta de gravacoes** =
`/mnt/ssd/pregacoes`.

### Opcao B - montagem automatica por UUID

```bash
lsblk -f                      # descubra o UUID do SSD
sudo mkdir -p /mnt/ssd
sudo bash -c 'echo "UUID=<seu-uuid> /mnt/ssd ext4 defaults,nofail 0 2" >> /etc/fstab'
sudo mount -a
```

`nofail` e essencial: se o SSD faltar, o Raspberry continua subindo.

### Seguranca

* o servico grava em `recordings/` por padrao;
* se o SSD estiver em `/mnt/ssd`, aponte a pasta de gravacoes para la;
* o sistema monitora o espaco livre e recusa iniciar gravacao abaixo de
  `storage.min_free_mb` (padrao 512 MB).

---

## 4. Verificar a instalacao

```bash
pregacao status
pregacao doctor
pregacao check          # precisa de interface USB conectada
```

`pregacao doctor` verifica diretorios, `arecord`, `ffmpeg`, interface de audio,
credenciais do Drive, PIN e se o servico esta respondendo.

---

## 5. Primeiro acesso pela interface

1. Descubra o IP: `hostname -I`
2. No celular, abra `http://<ip>:8080`
3. Informe o PIN (de `/opt/pregacao-recorder/.env`)
4. **CONFIG** -> confira a interface de audio detectada
5. **CONFIG -> TESTAR SINAL** - suba o fader da mesa ate aparecer sinal

---

## 6. Inicializacao automatica

Ja configurado pelo `install.sh`:

```
Raspberry OS -> systemd -> Recording Service -> Web API -> Interface web
```

```bash
systemctl status pregacao-recorder
# Restart=always + RestartSec=5
# After=network-online.target sound.target
# journalctl -u pregacao-recorder -f
```

Se o servico cair, o systemd reinicia em ate 5 segundos. Se o Raspberry
reiniciar no meio de uma gravacao, os segmentos ficam preservados e a interface
avisa na proxima abertura (veja [RECUPERACAO.md](RECUPERACAO.md)).

---

## 7. Atualizando a aplicacao

```bash
cd /home/pi/pregacao-recorder
git pull
sudo bash ./scripts/install.sh      # reinstala preservando .env e config.json
```

---

## 8. Desinstalando

```bash
sudo systemctl disable --now pregacao-recorder
sudo rm -f /usr/local/bin/pregacao /etc/systemd/system/pregacao-recorder.service
sudo systemctl daemon-reload
# /opt/pregacao-recorder pode ser removido manualmente depois de copiar as gravacoes
```

---

## Problemas comuns

| Sintoma | Causa provavel | Solucao |
|---|---|---|
| `pregacao status` diz "SERVICO FORA DO AR" | servico parado | `sudo systemctl start pregacao-recorder` |
| `Nenhuma interface de audio` | USB desconectado | `arecord -l`, `lsusb`, trocar cabo/porta |
| PIN nao funciona | `.env` alterado | `cat /opt/pregacao-recorder/.env` |
| Pasta cheia | SSD full | `pregacao status`, ajustar retencao |
| Interface nao abre | IP errado / roteador | `hostname -I`, teste com `curl http://<ip>:8080/api/ping` |
