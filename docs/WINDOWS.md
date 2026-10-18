# Windows - PC da igreja

O `pregacao-recorder` roda em Windows 10/11 com duas pecas ja adaptadas:

* captura de audio via **ffmpeg/DirectShow** (o `arecord` e so Linux);
* **agente MQTT** do controle remoto (`app/remote/agent.py`), o mesmo do Linux.

O restante (interface web, fila de upload, banco, eventos) e Python puro e
roda igual. As telas de Wi-Fi/rede do sistema sao do Raspberry e nao
funcionam no Windows (inofensivas; o PC usa a rede da casa normalmente).

## 1. Requisitos

| O que | Como instalar |
|---|---|
| Windows 10/11, sempre **logado** | - |
| Python 3.11+ | `winget install Python.Python.3.12` (ou python.org) |
| ffmpeg | `winget install Gyan.FFmpeg` (abra um PowerShell novo depois) |
| Microfone/mesa ligada | teste com o gravador de som do Windows |

## 2. Instalacao

1. Copie a pasta do projeto para o PC (ex.: `D:\Dev\pregacao-recorder`);
2. Abra PowerShell **dentro** da pasta:

   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

3. Copie `.env.example` para `.env` e preencha seguindo `docs/EMQX.md`:
   bloco REMOTO (host EMQX, usuario/senha do PC, `PREGACAO_OPERATOR_TOKEN`)
   e **`PREGACAO_DEVICE_ID=pregacao-igreja-01`** (obrigatorio no Windows:
   sem ele o codigo usa o hostname e o app fica OFFLINE).

## 3. Rodar

| Bat | O que sobe |
|---|---|
| **`iniciar-tudo.bat`** | agente MQTT (janela minimizada) + gravador - use este |
| `iniciar-gravador.bat` | so interface (`http://127.0.0.1:8080`) e captura |
| `iniciar-agente.bat` | so o agente (testes/validacao) |

Depois de abrir, confira:

1. `http://127.0.0.1:8080` abre a interface do gravador;
2. no log do agente: `[REMOTE] conectado a ...` (sem isso o celular fica OFFLINE);
3. celular: badge **ONLINE** e estado PRONTO/GRAVANDO em tempo real.

**Uma instancia so**: se dois agentes rodarem ao mesmo tempo, um derruba o
outro (mesmo client ID) e o app pisca OFFLINE/ONLINE. Feche janelas duplicadas.

## 4. Automatico ao ligar

```
schtasks /create /tn "Pregacao" /tr "\"D:\Dev\pregacao-recorder\iniciar-tudo.bat\"" /sc onlogon /rl highest
```

O usuario precisa estar logado (o PC da igreja fica direto no desktop).
Dica: Plano de energia -> nunca desligar tela/disco.

## 5. Audio (DirectShow)

* **Auto (padrao)**: o sistema escolhe a primeira interface, preferindo USB;
* **Fixar**: interface web -> Configuracoes -> audio (ou `audio.device` no
  config) com o nome EXATO, ex.: `Microfone (Mesa de Som USB)`;
* Listar nomes: `ffmpeg -list_devices true -f dshow -i dummy` (use a parte
  marcada com `(audio)`).

## 6. Problemas comuns

| Sintoma | Causa / solucao |
|---|---|
| `captura indisponivel ... ffmpeg nao encontrado` | `winget install Gyan.FFmpeg` e abra PowerShell novo |
| `[REMOTE] conexao recusada (rc=134)` | senha errada no `.env` |
| Celular OFFLINE | agente fechado? token errado no celular? EMQX -> Monitor -> Connections mostra `Estudo-DNMS`? |
| App pisca OFFLINE/ONLINE | duas instancias do agente - feche duplicadas |
| Aviso `/proc/mounts` no log | modulo de armazenamento do Linux; inofensivo no Windows |
| Upload do Drive | credenciais OAuth continuam o mesmo fluxo local (`credentials.json`) |
