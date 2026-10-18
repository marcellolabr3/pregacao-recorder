# CHECKLIST DE VALIDACAO

Rode esta lista **antes** de considerar o sistema em producao.
Marque cada item apenas depois de testar na pratica.

## Inicializacao

- [ ] Raspberry liga sozinho (energia -> boot -> servico ativo)
- [ ] servico inicia sozinho (`systemctl status pregacao-recorder`)
- [ ] interface web fica disponivel pelo celular (`http://pregacao-pi.local:8080`)
- [ ] PIN de acesso funciona
- [ ] assistente de primeiro acesso aparece sozinho na 1a vez
- [ ] assistente nao aparece de novo apos CONCLUIR CONFIGURACAO

## Audio

- [ ] interface USB detectada (`arecord -l` mostra o card)
- [ ] TESTAR AUDIO/TESTAR SINAL mostra sinal (nao SILENCIO)
- [ ] gravacao funciona (INICIAR -> GRAVANDO -> FINALIZAR)
- [ ] arquivo final existe e possui audio correto (ouvir o playback)
- [ ] sem interface USB, INICIAR e recusado com aviso claro

## Interface

- [ ] celular acessa pela rede local
- [ ] status PRONTO funciona
- [ ] iniciar funciona
- [ ] status GRAVANDO aparece sem recarregar a pagina
- [ ] cronometro funciona
- [ ] finalizar exige confirmacao ("Tem certeza que deseja finalizar a gravacao?")
- [ ] arquivo final e criado e aparece no HISTORICO
- [ ] HISTORICO mostra data, duracao, tamanho, status, upload e Drive

## Configuracoes avancadas

- [ ] CONFIGURACOES AVANCADAS pede PIN de administrador
- [ ] usuario comum nao altera audio/armazenamento/credenciais (HTTP 403)
- [ ] LOGS carregam na tela do administrador
- [ ] usuario final NAO ve Client ID nem Client Secret em CONFIG

## Armazenamento

- [ ] SSD montado automaticamente no boot (`lsblk`)
- [ ] gravacao permanece apos reboot
- [ ] espaco livre aparece na tela principal
- [ ] espaco insuficiente recusa nova gravacao

## Google Drive

- [ ] conectar conta funciona (abre a janela oficial do Google)
- [ ] usuario nao precisa informar Client ID
- [ ] usuario nao precisa informar Client Secret
- [ ] nenhuma senha do Google e digitada no equipamento
- [ ] status mostra CONECTADO + e-mail da conta + pasta
- [ ] TESTAR CONEXAO passa
- [ ] upload funciona (arquivo aparece no Drive)
- [ ] upload duplicado nao ocorre (historico marca ENVIADO uma unica vez)
- [ ] DESCONECTAR apaga o token e o sistema avisa
- [ ] reconectar (inclusive com outra conta) funciona

## Internet

- [ ] gravacao funciona sem internet
- [ ] upload fica PENDENTE (fila preservada)
- [ ] upload retoma quando a internet retorna (ou via REENVIAR FILA)
- [ ] nenhum arquivo e perdido durante a queda de internet

## Rede

- [ ] Ethernet e reconhecida sozinha (sem configuracao manual)
- [ ] painel REDE mostra IP e gateway da Ethernet
- [ ] PROCURAR REDES lista as redes visiveis e as mais fortes primeiro
- [ ] conectar com senha errada e recusado e o equipamento segue acessivel
- [ ] conectar em rede valida funciona (IP aparece no painel)
- [ ] a senha digitada nunca aparece na tela, no log nem na resposta da API
- [ ] sem Ethernet e sem Wi-Fi, a rede `PREGACAO-PI-XXXX` sobe sozinha
- [ ] Access Point de recuperacao **nao** e derrubado pelo watchdog enquanto durar
- [ ] com a rede de volta, o Access Point e desligado sozinho
- [ ] botao ATIVAR MODO DE CONFIGURACAO liga a rede de configuracao (com aviso)
- [ ] botao DESATIVAR desliga e devolve o Wi-Fi normal
- [ ] ligar/desligar o modo de configuracao nao interrompe gravacao em andamento
- [ ] o painel continua acessivel pelo IP local com o Access Point ativo
- [ ] Tailscale conectado (ACESSO REMOTO = CONECTADO)
- [ ] painel lista os 3 acessos: nome local, IP local e IP do Tailscale
- [ ] sem Tailscale autenticado, o painel mostra "autenticacao pendente" + link
- [ ] nenhum acesso exige abrir porta no roteador (sem port forwarding/UPnP)
- [ ] operacoes de rede exigem PIN de administrador (403 sem admin)

## Energia

- [ ] gravacao e iniciada
- [ ] Raspberry e desligado inesperadamente (puxar o cabo)
- [ ] Raspberry volta e o servico inicia sozinho
- [ ] gravacao interrompida e detectada (banner ATENCAO)
- [ ] arquivo e preservado/recuperado (RECUPERAR)
- [ ] interface informa o problema (cartao GRAVACAO INTERROMPIDA)

## Seguranca

- [ ] sem PIN, nada pode iniciar/finalizar/alterar
- [ ] interface so responde na rede local
- [ ] `.env` com PINs nao e acessivel pela interface web
- [ ] operacoes de rede (Wi-Fi, Access Point, Tailscale) pedem PIN de administrador
- [ ] a senha do Wi-Fi guardada nao e devolvida por nenhuma resposta da API
- [ ] a senha do Access Point so existe no `.env` (nunca em log, argv ou API)
- [ ] Access Point sempre tem senha (nao abre)

## Controle remoto (APK)

- [ ] `systemctl status pregacao-remote` ativo e habilitado
- [ ] log mostra `[REMOTE] conectado a ... (device_id=pregacao-igreja-01)`
- [ ] topic `avail` publica `online` retido (confira no painel do broker)
- [ ] topic `state` chega retido (quem assina ja ve o estado sem esperar)
- [ ] `STATUS` responde `ack` com `ok:true` e o estado atual
- [ ] `START` responde `ack` e inicia a gravacao (com audio conectado)
- [ ] `START` de novo responde `idempotent:true` e **nao** abre 2a gravacao
- [ ] `STOP` responde `ack` e encerra; `STOP` parado responde `idempotent:true`
- [ ] queda de Internet **nao** interrompe gravacao em andamento
- [ ] apos reiniciar o equipamento, o agente reconecta sozinho
- [ ] cartao CONTROLE REMOTO mostra ID, host e estado do servico
- [ ] usuario final nao ve o token do operador (apenas administrador)
- [ ] sem `PREGACAO_REMOTE_HOST`, o servico fica inativo e nada quebra
- [ ] audio nunca trafega pelo servico remoto (so comandos e estados)

## Documentos

- [ ] `DOCUMENTACAO.md` entregue
- [ ] `INSTALACAO-RASPBERRY.md` entregue
- [ ] `GUIA-USUARIO.md` entregue
- [ ] `docs/REDE.md` entregue
- [ ] `docs/AGENTE.md` entregue
- [ ] backup antes de atualizar foi testado (`./update.sh`)
- [ ] desinstalacao sem apagar gravacoes foi testada (`./uninstall.sh`)

---

### Como testar a queda de energia de verdade

1. Inicie uma gravacao e espere > 60 s (2 segmentos).
2. Sem finalizar, **puxe a fonte** do Raspberry.
3. Espere 10 s e ligue de novo.
4. Entre na interface: deve aparecer **ATENCAO / GRAVACAO INTERROMPIDA**.
5. Clique **RECUPERAR** e confira o arquivo no HISTORICO.

### Como testar a internet caida de verdade

1. Desconecte o cabo/roteador (ou bloqueie a saida).
2. Grave e finalize uma pregacao.
3. Veja **UPLOAD PENDENTE** e REDE OFFLINE.
4. Recone a internet.
5. O envio deve ocorrer sozinho - confira **ENVIADO** no HISTORICO.

### Como testar a recuperacao de rede de verdade

1. Com o equipamento na rede (Ethernet ou Wi-Fi), abra **CONFIG -> REDE**.
2. Desconecte o cabo e desligue o roteador (ou puxe o cabo da parede).
3. Aguarde ~12 s: o painel passa para **OFFLINE** e a rede `PREGACAO-PI-XXXX`
   aparece no celular. O Access Point foi levantado sozinho pelo watchdog
   (confira com `journalctl -u pregacao-netwatch -f`:
   `[NETWORK] Starting configuration AP`).
4. Conecte-se a essa rede com a senha do `.env` (padrao `pregacao12345`)
   e abra `http://192.168.50.1:8080`: o painel continua funcionando.
5. Restaure a rede original. Em ~15 s o Access Point e desligado sozinho
   (`[NETWORK] Stopping configuration AP`) e o IP local volta.
6. Confira que nenhuma gravacao nem upload se perdeu no processo.

### Como testar o acesso remoto (Tailscale)

1. **CONFIG -> REDE -> AUTENTICAR** (pede o PIN do administrador).
2. Abra o link de autenticacao e entre com a conta Tailscale da igreja.
3. O painel passa para **ACESSO REMOTO = CONECTADO** e lista
   `http://<ip tailscale>:8080` em **ACESSOS DO PAINEL**.
4. Em outro aparelho com o app Tailscale (mesma conta), fora do Wi-Fi da
   igreja (use o 4G), abra esse endereco: o painel deve carregar.
5. Nenhum passo acima exige abrir porta no roteador.

### Como testar o controle remoto (APK) de verdade

1. Confira no Pi: `systemctl status pregacao-remote` (**active (running)**)
   e `journalctl -u pregacao-remote -n 20` com a linha
   `[REMOTE] conectado a ... (device_id=pregacao-igreja-01)`.
2. No painel do broker (ex.: EMQX), assine `pregacao/<device_id>/#`:
   deve chegar `avail = online` e um `state` **retido**.
3. Publique `{"cmd":"STATUS","req_id":"t1"}` em `.../cmd` e espere o
   `ack` com `ok:true`.
4. Publique `{"cmd":"START","req_id":"t2"}` - com a Soundcraft conectada a
   gravacao comeca (sem audio, vem `ok:false` explicando o motivo).
5. Publique `START` de novo: a resposta tem `idempotent:true` e **nao**
   ha segunda gravacao (confira tambem no painel local).
6. Publique `{"cmd":"STOP","req_id":"t3"}`: encerra e responde `ok:true`.
7. Instale o APK (atual: `flutter/pregacao_controle/build/app/outputs/
   flutter-apk/app-release.apk`, versao 2.0+; legado: `android/
   PregacaoControle-1.4-debug.apk`, veja `docs/AGENTE.md` 13.4). Host, ID e
   usuario ja vem de fabrica - digite **so o token do operador** (cartao
   CONTROLE REMOTO). Confira a versao na barra superior e repita 4-6 pela
   tela do celular, com o celular fora do Wi-Fi da igreja (4G).
8. Durante uma gravacao, desligue a Internet da igreja: o APK mostra
   OFFLINE mas a gravacao continua; ao voltar, o upload retoma e o APK
   mostra ENVIANDO -> ENVIADO.
9. No menu, **REDES WI-FI DO EQUIPAMENTO**: a lista precisa trazer as redes
   que o RASPBERRY enxerga (nao as do celular). Toque numa rede, digite a
   senha e confira a conexao em CONFIG -> REDE. A senha nao fica salva no
   celular e o Wi-Fi do celular nao muda.

> Automatizado: `python -m pytest tests/test_remote_agent.py -q` e o
> validador `python scripts/emqx_check.py` (ciclo STATUS/START/STOP ponta a
> ponta, com as credenciais lidas do `.env`).
