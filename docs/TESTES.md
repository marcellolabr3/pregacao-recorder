# Testes e validacao

---

## 1. Testes automatizados

```bash
cd pregacao-recorder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest
```

Os testes usam um diretorio temporario (`PREGACAO_HOME`) - **nao** mexem em
`/opt/pregacao-recorder` nem no microSD.

### Cobertura

| Arquivo | O que valida |
|---|---|
| `tests/test_states.py` | maquina de estados, transicoes proibidas, sem estados conflitantes |
| `tests/test_wav.py` | cabecalho WAV e **reparo de segmento truncado** |
| `tests/test_layout.py` | estrutura `AAA/MM/AAAA-MM-DD_HHMMSS`, nomes seguros, espaco, retencao |
| `tests/test_config.py` | defaults, override, arquivo corrompido, caminhos |
| `tests/test_db.py` | sessoes, fila de upload idempotente, backoff, **persistencia apos reabrir** |
| `tests/test_recovery.py` | deteccao de queda de energia, sessao orfa, **nada apagado automaticamente**, consolidacao |
| `tests/test_events.py` | barramento de eventos/SSE |
| `tests/test_api.py` | PIN obrigatorio, recusa de start/stop invalidos, validacao de config, **PIN de administrador na area avancada**, assistente de 1o acesso, credenciais fora do alcance do usuario comum |
| `tests/test_audio.py` | `arecord -l`, deteccao de placa USB (regressao do parser de nomes com espaco) |
| `tests/test_recorder.py` | parada do capturer em cada SO (regressao do SIGINT no Windows) |
| `tests/test_manager.py` | finalizacao, recuperacao, descarte, **gravacao vazia nao vira ERRO** |
| `tests/test_network.py` | Ethernet, Wi-Fi, Access Point, watchdog e Tailscale (47 testes) |
| `tests/test_network_api.py` | API de rede protegida por PIN de administrador |
| `tests/test_remote_agent.py` | controle remoto: topics, comandos idempotentes, `ack`, prazo de validade (`ts`/TTL), estado retido, ciclo do servico e callbacks do paho (62 testes) |
| `tests/test_destinos.py` | destinos de gravacao: SSD e cartao SD, pontos de montagem, escolha valida (18 testes) |
| `tests/test_estudos.py` | autenticacao do NotebookLM: pre-flight, pausa AGUARDANDO, retomada, keepalive oficial, login visivel (14 testes) |
| `tests/test_main.py` | instancia unica do servidor (S0) |

Total: **292 testes**.

### Smoke test do servidor ligado

```bash
python3 -m app.main --port 8099 &
python3 scripts/smoke.py http://127.0.0.1:8099 <PIN> [PIN_ADMIN]
```

Verifica **21 pontos**: autenticacao, bloqueio de operacoes criticas,
gravacao curta real (start 200 com audio / 409 sem), validacao de config,
**bloqueio de config avancada sem administrador (403)**, recovery, fila de
upload, notificacoes e healthcheck.

---

## 2. Validacao obrigatoria: queda de energia

```bash
sudo ./scripts/power_loss_test.sh
```

Cenarios cobertos:

1. iniciar gravacao pela API;
2. **SIGKILL no servico** (simula corte);
3. reiniciar o servico;
4. confirmar que a gravacao interrompida foi detectada;
5. recuperar pela API;
6. confirmar o arquivo final.

### Checklist manual (fazer uma vez na instalacao)

| # | Passo | Esperado |
|---|---|---|
| 1 | INICIAR GRAVACAO pelo celular | banner `GRAVANDO`, cronometro subindo |
| 2 | abrir a pagina em **outro celular** | mostra `GRAVANDO` com a mesma duracao |
| 3 | aguardar 1 minuto e FINALIZAR (com confirmacao) | `FINALIZANDO` -> `PRONTO` |
| 4 | conferir o arquivo em `/mnt/ssd/pregacoes/AAA/MM/` | `.mp3` com data/hora do inicio |
| 5 | iniciar de novo e **puxar o cabo de energia** | - |
| 6 | religar e abrir a interface | painel `GRAVACAO INTERROMPIDA` com duracao |
| 7 | tocar em RECUPERAR | arquivo final criado, segmentos removidos |
| 8 | aguardar internet | `ENVIANDO` -> upload concluido no Drive |
| 9 | desligar o roteador durante o envio | `UPLOAD PENDENTE`, arquivo no SSD |
| 10 | religar o roteador | envio automatico retoma |
| 11 | `sudo reboot` no meio de uma gravacao | item de recuperacao apos o boot |
| 12 | desconectar a interface USB durante gravacao | `capture_gap` nos logs e reconexao |

---

## 3. Verificando que o audio esta sendo gravado

```bash
pregacao check                 # sinal real por 2 s
watch -n2 'ls -l /mnt/ssd/pregacoes/.sessions/*/'
pregacao status                # bytes e duracao crescendo
```

Depois de finalizar:

```bash
ffprobe -hide_banner /mnt/ssd/pregacoes/2026/09/<arquivo>.mp3
```

Esperado: `Duration: 00:MM:SS`, `Audio: mp3, 44100 Hz, stereo`.

---

## 4. Recursos no Raspberry Pi 3 B+

Monitoramento:

```bash
pregacao doctor
systemctl status pregacao-recorder
journalctl -u pregacao-recorder -f
free -h && uptime
```

Referencias esperadas (Raspberry Pi OS Lite, sem desktop):

| Recurso | Esperado |
|---|---|
| RAM do servico | 60-120 MB |
| CPU ocioso | < 3% |
| CPU gravando | 5-15% (a maioria e o `arecord`) |
| Disco | ~57 MB/hora a 128 kbps |

Se a RAM crescer apos longos periodos, verifique `pregacao logs -f` por erros
repetidos.

---

## 5. Testes de robustez

| Falha | Esperado |
|---|---|
| reboot | servico volta sozinho (`Restart=always`) |
| corte de energia | segmentos preservados + painel de recuperacao |
| internet fora | gravacao termina, upload pendente |
| Drive fora do ar | backoff automatico, nada perdido |
| USB desconectado | `capture_gap` + reconexao sem encerrar a sessao |
| SSD desconectado | erro claro no status; ao voltar, retoma |
| servico morto | systemd reinicia em 5 s |
| pasta quase cheia | recusa iniciar abaixo de `min_free_mb` |

---

## 6. Criterios de aceite do projeto

- [ ] `python -m pytest` verde (292 testes)
- [ ] `scripts/smoke.py` 21/21
- [ ] `pregacao doctor` sem XX
- [ ] `pregacao check` com sinal
- [ ] iniciar/finalizar pelo celular
- [ ] confirmacao obrigatoria no FINALIZAR
- [ ] dois celulares veem o mesmo estado
- [ ] `power_loss_test.sh` aprovado
- [ ] arquivo final reproduz com audio correto
- [ ] upload confirmado no Google Drive
- [ ] upload pendente retoma apos voltar a internet
- [ ] logs acessiveis por `pregacao logs`
