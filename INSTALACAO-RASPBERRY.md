# INSTALACAO NO RASPBERRY PI - passo a passo do zero

Este guia leva voce de um **Raspberry Pi 3 Model B+ de fabrica** ate o
sistema gravando. Nao e preciso saber programacao: siga na ordem.

### O que voce precisa ter em maos

* Raspberry Pi **3 Model B+**
* microSD de **16 GB ou mais** (classe 10)
* **Raspberry Pi OS Lite 64-bit** (gravado no passo 1)
* SSD ou HD USB com cabo (armazenamento das gravacoes)
* Interface de audio USB (ex.: Behringer UMC/FCA, Focusrite, etc.)
* Cabo de rede **ou** rede Wi-Fi conhecida
* Um computador para gravar o cartao e um celular/notebook na mesma rede
* Fonte oficial de 5V/2,5A do Raspberry

---

# PARTE 1 - Preparacao do sistema operacional

1. Instale o **Raspberry Pi Imager** no seu computador
   (https://www.raspberrypi.com/software/) e abra.
2. Clique em **CHOOSE DEVICE** -> selecione **Raspberry Pi 3**.
3. Clique em **CHOOSE OS** -> **Raspberry Pi OS (other)** ->
   **Raspberry Pi OS Lite (64-bit)** (sem area de trabalho - sobra mais
   memoria para gravar).
4. Clique em **CHOOSE STORAGE** -> selecione o microSD.
5. **ANTES de gravar**, clique no icone de engrenagem (ou `CTRL+SHIFT+X`)
   e configure:
   1. **Set hostname**: ex.: `pregacao-pi` (e o endereco `pregacao-pi.local`)
   2. **Enable SSH** -> marcado, com **password authentication**
   3. **Set username and password**: crie o usuario (ex.: `pi`) e uma
      senha forte - anote; e este usuario que voce usara no terminal
   4. **Configure wireless LAN**: rede Wi-Fi da igreja + pais/hora
   5. **Set locale**: pais e idioma
6. Clique em **WRITE** e aguarde concluir.
7. Retire o microSD e coloque no Raspberry.
8. Ligue o Raspberry (fonte, cabo de rede se usar, e deixe ligado ~2 min).
9. Descubra o IP: no roteador, ou no computador rode (Windows: PowerShell):

   ```bash
   ping pregacao-pi.local
   ```

   Se responder, voce ja tem o endereco. Se nao, veja a Parte 5 (IP).

10. Conecte via **SSH**. No Windows (PowerShell) ou Linux/Mac:

    ```bash
    ssh pi@pregacao-pi.local
    ```

    (troque `pi` pelo usuario que voce criou). Na primeira vez aceite a
    chave com `yes` e digite a senha. Pronto: voce esta dentro do terminal.

> Todo o restante e feito **dentro desse terminal por SSH**.

---

# PARTE 2 - Preparacao do armazenamento USB (SSD/HD)

> Regra: **nunca assuma que o disco e `/dev/sda1`** - sempre verifique.

1. Conecte o SSD/HD em uma das portas USB do Raspberry (de preferencia a
   porta USB 2 azul mais proxima da fonte).

2. Identifique o dispositivo:

   ```bash
   lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE
   ```

   Procure a linha do seu disco (ex.: `sda`, `sda1`). Anote o nome real.

3. **(Opcional) Formatar** - APENAS se o disco for novo ou puder apagar tudo.
   Substitua `/dev/sda1` pelo nome real que voce viu:

   ```bash
   sudo mkfs.ext4 -L pregacoes /dev/sda1
   ```

4. Crie o ponto de montagem:

   ```bash
   sudo mkdir -p /mnt/ssd
   ```

5. Descubra o identificador UNIQUE do sistema de arquivos (UUID):

   ```bash
   sudo blkid /dev/sda1
   ```

   Anote o valor de `UUID="..."`.

6. Configure a **montagem automatica** no boot:

   ```bash
   sudo nano /etc/fstab
   ```

   Adicione **uma linha** no final (cole o UUID que voce anotou):

   ```
   UUID=COLOQUE-AQUI-O-UUID  /mnt/ssd  ext4  defaults,noatime,nofail  0  2
   ```

   `nofail` permite que o Raspberry continue ligando mesmo se o SSD faltar.
   Salve: `CTRL+O`, `ENTER`, `CTRL+X`.

7. Monte e confira:

   ```bash
   sudo mount -a
   lsblk -o NAME,SIZE,MOUNTPOINT
   ```

   `/mnt/ssd` deve aparecer montado.

8. Permissoes para o usuario do servico (troque `pi` se usar outro):

   ```bash
   sudo chown pi:pi /mnt/ssd
   mkdir -p /mnt/ssd/pregacoes
   ```

9. **Teste de escrita:**

   ```bash
   dd if=/dev/zero of=/mnt/ssd/teste.bin bs=1M count=100 && rm /mnt/ssd/teste.bin && echo OK
   ```

10. **Teste apos reboot** (o disco deve continuar montado):

    ```bash
    sudo reboot
    # depois de voltar:
    ssh pi@pregacao-pi.local
    lsblk -o NAME,SIZE,MOUNTPOINT
    ```

---

# PARTE 3 - Preparacao da interface de audio USB

1. Conecte a interface USB (de preferencia na porta USB 2) e verifique se o
   Linux reconheceu:

   ```bash
   lsusb
   ```

   A interface deve aparecer na lista.

2. Liste os dispositivos ALSA:

   ```bash
   arecord -l
   ```

   Exemplo de saida:

   ```
   card 1: UMC202HD [Behringer UMC202HD], device 0: USB Audio [USB Audio]
     Subdevices: 1/1
     Subdevice #0: subdevice #0
   ```

   Neste exemplo: `card 1` -> device `hw:1,0`.

3. **Teste de entrada** (2 segundos, gravando em `/tmp`):

   ```bash
   arecord -D hw:1,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/teste.wav
   aplay /tmp/teste.wav
   ```

   Toque a mesa durante a gravacao do teste: voce deve ouvir o que tocou.
   Se tocar ruido, confira a mesa (fader, canal, MUTE).

4. **Nao ha nome fixo**: cada interface tem um `card` diferente. Descubra o
   seu sempre com `arecord -l`.

5. Configure o sistema: a interface pode ser deixada em **AUTO** (o sistema
   detecta) ou fixada nas `CONFIGURACOES AVANCADAS -> AUDIO` da interface
   web (`hw:1,0`).

6. **Gravacao de teste** pela interface web: abra no celular, PIN,
   **TESTAR SINAL** (mostra o pico em dBFS) e faca uma gravacao de 10 s com
   INICIAR -> FINALIZAR. Confira o arquivo no historico e ouca o playback.

> Dica: se a interface for desconectada durante a gravacao, o sistema entra
> em erro/atencao e os segmentos ja gravados ficam preservados.

---

# PARTE 4 - Instalacao do aplicativo

O objetivo e este fluxo:

```
copiar o projeto para o Raspberry
        |
        v
executar ./install.sh
        |
        v
dependencias instaladas -> diretorios criados -> permissoes configuradas
        |
        v
servico systemd criado -> habilitado -> iniciado
```

### 4.1 Copiar o projeto

Pelo computador, copie a pasta do projeto para o Raspberry (escolha UM):

**Opcao A - scp (Windows, Linux ou Mac):** no computador, na pasta do
projeto:

```bash
scp -r pregacao-recorder pi@pregacao-pi.local:~/
```

**Opcao B - pen drive / descompressor:** copie a pasta para um pendrive,
plugue no Raspberry e mova (no terminal do Raspberry):

```bash
# exemplo: pendrive montado em /media/pi/PEN
sudo cp -r /media/pi/PEN/pregacao-recorder ~/
sudo chown -R pi:pi ~/pregacao-recorder
```

**Opcao C - git:**

```bash
git clone <URL-DO-REPOSITORIO> ~/pregacao-recorder
```

### 4.2 Executar a instalacao

No terminal do Raspberry:

```bash
cd ~/pregacao-recorder
chmod +x install.sh update.sh uninstall.sh
sudo ./install.sh
```

O script faz **tudo** automaticamente:

* instala pacotes (`python3`, `alsa-utils`, `ffmpeg`, `rsync`...);
* copia o projeto para `/opt/pregacao-recorder`;
* cria `venv` e instala as dependencias Python;
* gera o `.env` com **PIN de acesso** e **PIN de administrador**
  (aparece no final da instalacao - **anote!**);
* configura permissoes;
* cria, habilita e inicia o servico `pregacao-recorder.service`;
* instala o comando `pregacao`.

Ao final imprime:

```
=== instalacao concluida ===
  servico    : systemctl status pregacao-recorder.service
  interface  : http://<IP>:8080
  PINs       : veja /opt/pregacao-recorder/.env
```

### 4.3 Servico systemd

O servico ja fica criado em `/etc/systemd/system/pregacao-recorder.service`.
Ele **sobe sozinho no boot**, **espera a rede**, **reinicia em caso de
falha** (`Restart=always`) e **registra logs** - nao depende de terminal
aberto. Comandos uteis:

```bash
sudo systemctl enable pregacao-recorder     # inicia junto com o boot
sudo systemctl start pregacao-recorder      # inicia agora
sudo systemctl status pregacao-recorder     # ve se esta ativo
sudo systemctl restart pregacao-recorder    # reinicia
journalctl -u pregacao-recorder -n 100      # ultimos logs
journalctl -u pregacao-recorder -f          # logs ao vivo
```

A instalacao cria tambem dois servicos auxiliares (ambos habilitados):

| Servico | Funcao |
|---|---|
| `pregacao-netwatch` | watchdog de rede: rede caiu -> Access Point de recuperacao |
| `pregacao-remote` | controle remoto (APK); **fica inativo** ate preencher `PREGACAO_REMOTE_HOST` no `.env` |

```bash
systemctl status pregacao-recorder pregacao-netwatch pregacao-remote
```

### 4.4 Primeiro acesso

1. Abra a interface pelo celular: `http://<IP>:8080` (ou `http://pregacao-pi.local:8080`).
2. Digite o PIN (o `.env`, secao `PREGACAO_PIN`).
3. O **ASSISTENTE DE PRIMEIRO ACESSO** abre sozinho:
   1. **Audio** - escolha a interface e clique em TESTAR AUDIO;
   2. **Armazenamento** - confira a pasta (`/mnt/ssd/pregacoes`);
   3. **Google Drive** - CONECTAR GOOGLE DRIVE (pode pular);
   4. **Finalizacao** - CONCLUIR CONFIGURACAO.
4. Depois disso o sistema inicia normalmente e **nao pede nada de novo**.

### 4.5 Google Drive (uma unica vez, administrador)

As credenciais do Google sao cadastradas **so pelo administrador**, uma vez:

* recomendado: coloque o JSON do OAuth em
  `/opt/pregacao-recorder/config/google_credentials.json`; **ou**
* preencha `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` no `.env`; **ou**
* use `CONFIGURACOES AVANCADAS -> GOOGLE DRIVE (TECNICO)` na interface
  (PIN de administrador).

Depois, **qualquer usuario** so usa o botao **CONECTAR CONTA GOOGLE**.
Detalhes: `docs/GOOGLE_DRIVE.md`.

---

# PARTE 5 - Acesso pelo celular

1. Confira se o Raspberry e o celular estao na **mesma rede** (Wi-Fi da
   igreja ou cabo + roteador).
2. Descubra o endereco:
   * hostname: `http://pregacao-pi.local:8080` (funciona na maioria dos
     celulares com mDNS);
   * ou o IP: `http://192.168.x.x:8080` - descubra com (no Raspberry):

     ```bash
     hostname -I
     ```

     ou olhe o dispositivo conectado no roteador.
3. Abra no **navegador** (Chrome, Safari...). Nao ha aplicativo para
   instalar em Android nem iPhone nesta versao - a interface web e o app.
4. Salve nos favoritos/na tela inicial do celular para abrir direto.

### Rede (Ethernet, Wi-Fi, Access Point e acesso remoto)

* **Ethernet**: reconhecida sozinha - basta plugar o cabo.
* **Wi-Fi**: `CONFIG -> REDE -> PROCURAR REDES` (pede o PIN do
  administrador) -> escolher a rede -> digitar a senha -> **CONECTAR**.
* **Sem nenhuma rede util**: o equipamento emite sozinho a rede
  `PREGACAO-PI-XXXX` (senha padrao `pregacao12345`). Conecte o celular e
  abra `http://192.168.50.1:8080` para configurar. Com a rede normal de
  volta, essa rede some sozinha.
* **Modo de configuracao na mao**: `CONFIG -> REDE -> ATIVAR MODO DE
  CONFIGURACAO` (com aviso) e `DESATIVAR` para voltar ao normal.
* **Acesso remoto (Tailscale)**: `CONFIG -> REDE -> AUTENTICAR`, entre com a
  conta Tailscale e copie o endereco `http://100.x.x.x:8080` listado em
  ACESSOS DO PAINEL. Com o app Tailscale no celular (mesma conta), esse
  endereco funciona de qualquer lugar - **sem abrir porta no roteador**.

Verificacao rapida, no Raspberry:

```bash
systemctl status pregacao-netwatch pregacao-recorder pregacao-remote
journalctl -u pregacao-netwatch -n 30
```

A instalacao ja configura NetworkManager, polkit, sudoers do Tailscale,
avahi (`pregacao-pi.local`) e o watchdog - nenhum passo adicional e
necessario. Detalhes, API e testes: `docs/REDE.md`.

Para ligar o **controle remoto pelo celular** (opcional), preencha
`PREGACAO_REMOTE_HOST` no `/opt/pregacao-recorder/.env` e reinicie com
`sudo systemctl restart pregacao-remote` - passo a passo em
`docs/AGENTE.md`.

---

# PARTE 6 - Como levar o sistema pronto para OUTRO Raspberry Pi

## Metodo A - instalacao limpa (recomendado)

Repetir as Partes 1 a 4 em outro equipamento:

```
Raspberry Pi OS Lite 64-bit  +  copia do codigo  +  ./install.sh
```

O `install.sh` gera PINs novos e recria a estrutura. Depois:

* cole o mesmo `config/google_credentials.json` (credenciais do app);
* conecte a conta Google de novo (o token e por equipamento);
* refaca o assistente de primeiro acesso.

## Metodo B - imagem/clonagem

1. No Raspberry ja configurado, pare o servico e desligue:

   ```bash
   sudo systemctl stop pregacao-recorder
   sudo poweroff
   ```

2. Tire o microSD e crie uma imagem no computador com o **Win32DiskImager**
   (Windows) ou `dd` (Linux): le o cartao inteiro e salva `.img`.

3. Grave essa `.img` em outros microSD - o sistema ja veio pronto
   (mesmos PINs, mesmas configuracoes, Drive conectado).

4. **Configuracoes que DEVEM ser alteradas em cada equipamento novo:**
   * `hostname` (para nao haver dois `pregacao-pi.local`);
   * `PREGACAO_PIN` e `PREGACAO_ADMIN_PIN` em `/opt/pregacao-recorder/.env`;
   * `PREGACAO_SECRET` (novo valor - assina as sessoes);
   * reconectar o Google Drive (opcional: pode-se manter a mesma conta);
   * `device_name` na interface (nome do local);
   * apagar o historico antigo, se desejado
     (`/opt/pregacao-recorder/data/`).

   Depois: `sudo systemctl restart pregacao-recorder`.

> Metodo A e mais simples de manter; metodo B e mais rapido para varios
> equipamentos iguais.

---

# PARTE 7 - Pacote de deploy

A pasta do projeto ja vem pronta para ser levada a qualquer Raspberry,
sem IDE, sem PyCharm, sem VS Code:

```
pregacao-recorder/
├── app/                    # codigo da aplicacao
├── scripts/                # utilitarios (wrappers dos scripts da raiz)
├── systemd/                # definicao do servico
├── config/                 # valores de fabrica + credenciais (local)
├── web/                    # interface (HTML/CSS/JS)
├── install.sh              # instala tudo
├── update.sh               # atualiza sem apagar dados
├── uninstall.sh            # desinstala (nunca apaga gravacao sem confirmar)
├── .env.example            # modelo do arquivo de segredos
├── README.md
├── DOCUMENTACAO.md
├── INSTALACAO-RASPBERRY.md
├── GUIA-USUARIO.md
└── CHECKLIST.md
```

Unico requisito no Raspberry: rodar `sudo ./install.sh` (o script instala o
Python e tudo o mais que faltar).

---

# PARTE 8 - Atualizacao

```bash
# 1. copie a nova versao para a pasta ~/pregacao-recorder-nova
# 2. rode:
cd ~/pregacao-recorder-nova
sudo ./update.sh
```

O que `update.sh` faz:

1. **backup** de `.env`, `config/`, `data/` e `logs/` para
   `/var/backups/pregacao-recorder/backup-<data>.tar.gz`;
2. para o servico;
3. copia **apenas o codigo** (preserva gravacoes, configuracoes, token do
   Google e historico);
4. atualiza as dependencias Python;
5. reinicia e confere se o servico subiu.

Para restaurar um backup:

```bash
sudo tar -xzf /var/backups/pregacao-recorder/backup-<data>.tar.gz -C /opt/pregacao-recorder
```

---

# PARTE 9 - Desinstalacao

```bash
cd ~/pregacao-recorder
sudo ./uninstall.sh          # remove o programa e MANTEM as gravacoes
sudo ./uninstall.sh --tudo   # remove tudo - pede confirmacao digitando SIM
```

**A desinstalacao nunca apaga gravacoes automaticamente.** Para apagar, e
preciso digitar exatamente `SIM` e o nome do servico - duas confirmacoes.

---

# PARTE 10 - Problemas comuns

| Sintoma | Causa provavel | Solucao |
|---|---|---|
| `arecord -l` vazio | interface desconectada/reconectada | replugue e rode de novo |
| "Nenhuma interface de audio encontrada" | USB/energia | outra porta USB, fonte melhor |
| SSD nao monta | `fstab` errado | refaça Parte 2 (UUID!) |
| Celular nao abre a pagina | redes diferentes | mesmo Wi-Fi; teste o IP |
| `pregacao-pi.local` nao resolve | mDNS bloqueado | use o IP (`hostname -I`) |
| Wi-Fi nao conecta | senha errada | refaca o passo com a senha correta |
| Rede `PREGACAO-PI-XXXX` nao aparece | ainda em tolerancia | espere ~45 s e acompanhe `journalctl -u pregacao-netwatch -f` |
| Access Point liga e desliga sozinho | ligado fora do painel | use `ATIVAR MODO DE CONFIGURACAO` (mantem a flag ligada) |
| Celular nao chega em `192.168.50.1` | senha do AP trocada | confira `PREGACAO_AP_PASSPHRASE` no `.env` |
| Acesso remoto nao abre | Tailscale deslogado | `CONFIG -> REDE -> AUTENTICAR` |
| Log mostra `sudo: no new privileges` | unit com `NoNewPrivileges` | rode `sudo ./update.sh` de novo |
| Servico cai | veja o log | `journalctl -u pregacao-recorder -n 100` |
| Drive nao conecta | credenciais/redirect | `docs/GOOGLE_DRIVE.md` |
| "502" na interface | servico parado | `sudo systemctl restart pregacao-recorder` |

Proximos passos: `CHECKLIST.md` (validacao completa).
