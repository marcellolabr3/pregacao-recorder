# REDE - Ethernet, Wi-Fi, Access Point e acesso remoto

Esta camada mantem o equipamento **sempre alcancavel pelo celular**, mesmo sem
cabo, sem Wi-Fi e sem Internet, e permite acesso remoto **sem abrir nenhuma
porta no roteador**.

Tudo e configuravel pela propria interface (CONFIG -> REDE) - nao precisa de
monitor, teclado ou mouse no Raspberry.

---

## 1. Resumo em uma frase

Ethernet e Wi-Fi sao detectados sozinhos; se o equipamento ficar sem nenhuma
rede util, ele emite a propria rede `PREGACAO-PI-XXXX` para voce se conectar e
configurar; e o Tailscale abre um tunel privado para voce acessar o painel de
qualquer lugar do mundo.

---

## 2. Componentes

| Parte | Arquivo | O que faz |
| --- | --- | --- |
| nmcli wrapper | `app/network/nm.py` | Ethernet, Wi-Fi, scan, conectar, Access Point |
| watchdog | `app/network/watchdog.py` | decide quando ligar/desligar o Access Point |
| conectividade | `app/network/connectivity.py` | teste de Internet (HTTPS + fallback 1.1.1.1 / 8.8.8.8) |
| Tailscale | `app/network/tailscale.py` | status, autenticacao e teste de acesso remoto |
| status do painel | `app/network/status.py` | monta o payload da tela REDE |
| API | `app/api/network_routes.py` | 12 endpoints HTTP (secao 6) |
| servico web | `systemd/pregacao-recorder.service` | servidor (`0.0.0.0:8080`) |
| watchdog | `systemd/pregacao-netwatch.service` | roda ANTES do servico web |
| polkit | `system/50-pregacao-network.rules` | deixa o servico mandar no NetworkManager |
| sudoers | `system/sudoers-pregacao-network` | lista fechada de comandos do Tailscale |
| avahi | `system/avahi-pregacao-http.service` | nome `pregacao-pi.local` na rede local |

Ordem de boot: **rede -> Access Point (se necessario) -> web -> gravacao**.

---

## 3. Ethernet

* Detectada automaticamente (NetworkManager), nenhuma configuracao manual.
* Enquanto existir Ethernet funcional, **nenhum outro caminho e ativado**
  (nem Wi-Fi de cliente, nem Access Point).
* Aparece no painel com IP e gateway.

## 4. Wi-Fi (cliente)

* Scan pela interface (`PROCURAR REDES`), listado por sinal (mais forte no topo).
* Conexao pede PIN de **administrador** e a senha nunca aparece em log,
  em argv de processo nem na resposta da API.
* Senha errada -> `409` com aviso claro, e o equipamento **continua acessivel**
  (a operacao reativa o Access Point se ele estava ativo).
* As credenciais ficam salvas no NetworkManager (senha leitura nunca e
  devolvida pela interface).

## 5. Access Point de configuracao

| Item | Valor |
| --- | --- |
| SSID | `PREGACAO-PI-XXXX` (`PREGACAO_AP_SSID` para mudar) |
| Senha WPA2 | `pregacao12345` (`PREGACAO_AP_PASSPHRASE`) |
| Endereco | `192.168.50.1/24` |
| Perfil NetworkManager | `pregacao-ap` (autoconnect desligado) |
| Painel no celular | `http://192.168.50.1:8080` |

Quando ele sobe sozinho:

1. Nao ha Ethernet;
2. nao ha Wi-Fi conectado;
3. passou a tolerancia: **45 s** se existe rede salva tentando reconectar,
   **12 s** se nao ha nada configurado (instalacao nova).

Enquanto existir Ethernet ou Wi-Fi util, o Access Point e **desligado**
automaticamente. A tabela de decisao completa esta em `evaluate()`
(`app/network/watchdog.py`):

| ap_forced | rede util | AP ativo | acao |
| --- | --- | --- | --- |
| ligado | - | nao | `ap_on` |
| ligado | - | sim | `keep` |
| desligado | sim | sim | `ap_off` |
| desligado | sim | nao | `keep` |
| desligado | nao | sim | `keep` |
| desligado | nao | nao (passou a tolerancia) | `ap_on` |

`ap_forced` e a flag `network.ap_forced`, que a API liga quando voce aperta
**ATIVAR MODO DE CONFIGURACAO**. A flag e relida pelo watchdog **por ultimo**,
ja na hora de agir - assim, se voce ligar (ou desligar) o modo pelo celular
enquanto um ciclo roda, o AP recem-ligado **nao e derrubado** nem o
recem-desligado e religado.

### Por que o Access Point precisa de "PMF desligado"

O driver Broadcom do Raspberry Pi 3 B+ recusa a chave IGTK exigida pelo
802.11w ao montar o hotspot: o `wpa_supplicant` aborta com
`key setting validation failed` e o NetworkManager derruba a ativacao com
`Hotspot network creation took too long` (issue raspberrypi/linux#7247).
Por isso o perfil usa `802-11-wireless-security.pmf 1` (desligado). Nao tente
ativar o 802.11w no Access Point - ele nao sobe.

O perfil **e sempre recriado** quando o AP esta parado, garantindo SSID e
senha atuais do `.env`, e a senha e passada **por stdin** (nunca em argv).

---

## 6. API (secao 17)

| Metodo | Rota | Acesso |
| --- | --- | --- |
| GET | `/api/network/status` | sessao |
| POST | `/api/network/connectivity-test` | sessao |
| GET | `/api/network/tailscale/status` | sessao |
| GET | `/api/network/wifi/scan` | administrador |
| POST | `/api/network/wifi/connect` | administrador |
| POST | `/api/network/wifi/disconnect` | administrador |
| POST | `/api/network/wifi/forget` | administrador |
| GET | `/api/network/wifi/saved` | administrador |
| POST | `/api/network/ap/enable` | administrador |
| POST | `/api/network/ap/disable` | administrador |
| POST | `/api/network/tailscale/login` | administrador |
| POST | `/api/network/tailscale/test` | administrador |

Sem sessao -> `401`. Com sessao mas sem PIN de administrador -> `403`
(`admin_obrigatorio`). As operacoes sao serializadas por um lock: se voce
apertar um botao enquanto outro processo mexe na rede, a resposta e `409`.

---

## 7. Acessos do painel

A tela REDE lista os enderecos que funcionam no momento:

* `http://pregacao-pi.local:8080` - nome local (avahi)
* `http://<ip local>:8080` - IP da Ethernet ou Wi-Fi
* `http://192.168.50.1:8080` - Access Point de configuracao (so com AP ativo)
* `http://<ip tailscale>:8080` - acesso remoto (so com Tailscale conectado)

O servidor escuta em `0.0.0.0` (variavel `PREGACAO_HOST`), ou seja, em todas
as interfaces - por isso todos os enderecos acima funcionam.

---

## 8. Tailscale (acesso remoto)

* Instalado pelo `install.sh` pelo repositorio oficial; `tailscaled` habilitado.
* O servico roda `tailscale ...` com `sudo -n` e uma **lista fechada** de
  subcomandos em `/etc/sudoers.d/pregacao-network` (validada com `visudo -c`).
* Fluxo no painel: **AUTENTICAR** -> link de autenticacao -> entrar com a
  conta da igreja -> painel passa para `ACESSO REMOTO = CONECTADO`.
* Depois disso aparece `http://<ip>:8080` em ACESSOS DO PAINEL, utilizavel
  pelo celular com o app Tailscale (mesma conta) mesmo fora da igreja (4G).

**Nao ha port forwarding, nao ha UPnP, nenhuma porta e aberta no roteador.**
O trafego vai por tunel criptografado entre os dispositivos da conta.

> **Tailscale nao e o controle remoto do APK.** O Tailscale serve para **abrir
> o painel** de fora; o APK controla o equipamento por outro caminho (conexao
> de saida do proprio Raspberry para um servico remoto), sem depender do
> Tailscale nem de conta adicional - ver `docs/AGENTE.md`. Os dois coexistem
> e nenhum dos dois exige abrir porta.

> O unit do servico web **nao** usa `NoNewPrivileges`: esse endurecimento
> bloqueia binarios setuid (`sudo`) e quebraria a API do Tailscale. Os demais
> endurecimentos (`PrivateTmp`, `ProtectSystem`) continuam ativos.

---

## 9. Logs

Saida para o journal com as tags `[NETWORK]` e `[TAILSCALE]`:

```bash
journalctl -u pregacao-netwatch -f      # watchdog (a cada 15 s)
journalctl -u pregacao-recorder -f      # acoes feitas pelo painel
```

Mensagens de transicao (somente o dono que as escreve):

```
[NETWORK] Ethernet connected
[NETWORK] Ethernet disconnected
[NETWORK] Wi-Fi connected: {ssid}
[NETWORK] Wi-Fi disconnected
[NETWORK] Internet available
[NETWORK] Internet unavailable
[NETWORK] Starting configuration AP
[NETWORK] Configuration AP active
[NETWORK] Stopping configuration AP
[NETWORK] Wi-Fi connection failed
[TAILSCALE] Connected
[TAILSCALE] Disconnected
```

Acoes e erros sao registrados por quem executa (`nm.py`, `network_routes.py`),
por exemplo `[NETWORK] Modo de configuracao Wi-Fi ativado pelo painel`.

---

## 10. Configuracao

No arquivo `/opt/pregacao-recorder/.env`:

| Variavel | Padrao | Descricao |
| --- | --- | --- |
| `PREGACAO_HOST` | `0.0.0.0` | interface de escuta do servidor |
| `PREGACAO_PORT` | `8080` | porta do painel |
| `PREGACAO_AP_SSID` | vazio | vazio = `PREGACAO-PI-XXXX` automatico |
| `PREGACAO_AP_PASSPHRASE` | `pregacao12345` | senha WPA2 do Access Point |
| `PREGACAO_NETWATCH_INTERVAL` | `15` | segundos entre ciclos do watchdog |

Na interface (CONFIGURACOES AVANCADAS): host/porta do teste de Internet e
tempo de retry.

---

## 11. Comandos uteis (SSH)

```bash
# estado geral
nmcli device status
nmcli connection show --active
ip -4 addr show eth0 wlan0

# Access Point
nmcli connection show pregacao-ap
iw dev wlan0 info | head -5          # deve mostrar "type AP"

# watchdog / logs
systemctl status pregacao-netwatch
journalctl -u pregacao-netwatch -n 50

# Tailscale
tailscale status
tailscale ip -4

# testes automatizados
cd /home/<usuario>/pregacao-recorder
/opt/pregacao-recorder/.venv/bin/python -m pytest -q
```

---

## 12. Testes

### Automatizados

```bash
cd /home/<usuario>/pregacao-recorder
/opt/pregacao-recorder/.venv/bin/python -m pytest -q
```

Os testes de rede cobrem: decisao do Access Point, ativacao/recriacao do
perfil, senha nunca em argv, watchdog sem corrida com o painel, status sem
contar o proprio AP como Wi-Fi de cliente, API (401/403/409), Tailscale e
o fluxo de recuperacao.

### Manual (uma vez na instalacao)

1. Ethernet reconhecida sozinha; IP aparece no painel.
2. `PROCURAR REDES` lista redes; senha errada devolve aviso e nada quebra.
3. Puxe o cabo e desligue o roteador -> em ~12 s a rede `PREGACAO-PI-XXXX`
   aparece; conecte e abra `http://192.168.50.1:8080`.
4. Restaure a rede -> o AP e desligado sozinho.
5. **ATIVAR MODO DE CONFIGURACAO** liga o AP com aviso; **DESATIVAR** desliga.
6. AUTENTICAR no Tailscale -> `ACESSO REMOTO = CONECTADO` e a URL remota
   aparece; teste pelo celular com 4G e o app Tailscale.
7. Reinicie o Raspberry -> tudo volta sozinho (`systemctl status`).

---

## 13. Solucao de problemas

| Sintoma | Causa provavel | Solucao |
| --- | --- | --- |
| `Wi-Fi` fica em "indisponivel" | NetworkManager parado | `systemctl status NetworkManager` |
| `nmcli` pede permissao | polkit ausente | reinstalar `50-pregacao-network.rules` e reiniciar o servico |
| AP nao sobe | driver recusou PMF/802.11w | conferir `802-11-wireless-security.pmf 1` no perfil |
| AP sobe e cai | flag `network.ap_forced` desligada com rede util | usar o botao do painel (liga a flag) |
| Tailscale "sem permissao" | sudoers ausente ou unit com `NoNewPrivileges` | reinstalar `/etc/sudoers.d/pregacao-network` |
| Tailscale "autenticacao pendente" | login nao concluido | painel -> AUTENTICAR -> abrir o link |
| `/api/stream` derruba o fluxo | header `Connection` na resposta | proibido pela PEP 3333 (corrigido, ha teste) |
| Painel nao carrega nada | PIN errado ou servico parado | `systemctl status pregacao-recorder` |

### Por que NAO usar `subject.local` na regra do polkit

O servico systemd e os processos iniciados por `runuser` nao possuem sessao
logind ativa, entao `subject.local` e `false` e a regra falharia. A regra
validada em hardware usa apenas `subject.user == "<usuario>"` combinado ao
prefixo `org.freedesktop.NetworkManager.`.

### Por que nao configurar firewall

Nao ha porta aberta no roteador da igreja (o painel so e alcancavel na rede
local e, para fora, apenas pelo tunel do Tailscale). Regras de firewall foram
avaliadas e **nao** adicionadas: elas quebrariam a descoberta local (avahi),
o DHCP do Access Point e a propria conexao Tailscale, sem ganho de seguranca
nessa topologia. Se a rede da igreja mudar, revise esta decisao.
