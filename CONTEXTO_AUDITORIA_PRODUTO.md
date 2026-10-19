# Contexto de auditoria e revisao do produto

Data: 19/10/2026. Projeto: `D:\Dev\pregacao-recorder`.

Este arquivo registra a auditoria de leitura e permite revisar o escopo. Nao e uma autorizacao para executar correcoes ou exclusoes. Nenhuma credencial deve ser registrada aqui.

## Atualizacao apos a retirada (19/10/2026)

O usuario autorizou implementar a retirada em tres sprints. O registro abaixo
continua como evidencia historica da auditoria; a coluna Decisao nao substitui
esta atualizacao de estado:

- A01-A04/A10: corrigidos; navegador real abriu sem erro JS e sem card de rede.
- A05-A08: resolvidos; servidor atualizado apos conferir ociosidade e rotas
  de integracoes/pregacoes/modelo retornando 200.
- A09: fluxo de renovacao corrigido com sessao nova, monitoramento e checagem passiva;
  entrada real na conta ainda precisa de validacao. Dois jobs preservados na ultima checagem.
- B01-B19: gestao Linux, comandos de rede, ALSA, servicos e instaladores retirados;
  armazenamento, home, CLI, exemplos e manuais adaptados ao Windows.
- B20: contexto operacional novo em `docs/CODEX_CONTEXT.md`; `CONTEXTO.md` agora aponta para ele; notas antigas com credenciais
  preservadas em `docs/CODEX_CONTEXT.local.md` (ignorado), sem uso como escopo.
- D16: inicio consolidado em um BAT; gravador/agente sem consoles extras.
  A janela do iniciador pode aparecer durante a subida; ver `docs/WINDOWS.md`.
- C01-C16 e demais D continuam fora desta tarefa; nao foram concluidos por esta retirada.
- F01-F04/F08: documentacao corrente revisada, mas provas reais/manual com capturas
  e funcionalidades pendentes continuam pendentes. PDF explicativo foi regenerado.
- F05: fonte Kotlin preservada como legado, sem tela Wi-Fi; nenhum APK foi gerado.
- Validacao da retirada: 268 testes; suite atual com 309 testes Python verdes em
  copia isolada, incluindo inicio/login. Navegador simulado passou; ver `docs/TESTES.md`.
- Plano, lista de arquivos e limites: `docs/REMOCAO_RASPBERRY.md`.

## Orientacao confirmada pelo usuario

- O produto sera utilizado no Windows.
- O Raspberry Pi deixou de fazer parte do produto; o usuario informou que ja havia solicitado sua retirada.
- O usuario pediu analise sem modificar o sistema. Depois, autorizou criar este arquivo.
- Outros pedidos antigos so podem ser considerados confirmados quando houver registro. Nao presumir que todo recurso listado abaixo foi rejeitado pelo usuario.
- MQTT e controle pelo celular tambem funcionam no Windows: nao excluir automaticamente junto com o Raspberry.

## Como revisar

Preencher a coluna **Decisao** com `MANTER`, `REMOVER`, `CORRIGIR`, `CONCLUIR` ou `ADIAR`; acrescentar observacoes quando necessario. `Pendente` significa que ainda falta decidir. Os itens Raspberry estao identificados para retirada conforme a orientacao atual, mas este documento nao executa a retirada.

As classificacoes distinguem: observacao na instancia aberta; defeito reproduzido; evidencia de codigo; pendencia documental; sugestao de simplificacao. Ausencia de teste real nao significa que a funcionalidade esteja quebrada.

## Validacao realizada

- Leitura de codigo, documentacao e configuracoes pertinentes, sem registrar valores secretos.
- Consultas GET ao servidor `http://127.0.0.1:8080` e abertura em navegador automatizado, sem iniciar gravacao ou envio.
- **342 testes Python passaram** em copia temporaria isolada, com banco e configuracoes de teste.
- Reproducoes de dados invalidos, sobrescrita e importacao parcial somente em banco temporario.
- `node --check web/static/app.js` passou; isso valida sintaxe, nao funcionamento no navegador.
- Nao foram executados testes Flutter, gravacao real, envio ao Drive/WhatsApp, comandos MQTT ou renovacao de login.
- Git estava limpo antes da criacao deste documento. O resultado dos testes nao elimina as falhas de interface descritas abaixo.

## A. Falhas observadas na instancia aberta

| ID | Achado e evidencia | Efeito | Decisao |
|---|---|---|---|
| A01 | Navegador registra `Cannot read properties of null (reading 'addEventListener')`. | Inicializacao do painel interrompida. | Pendente |
| A02 | `pregacaoForm` esta dentro de `advancedForm`; o navegador descarta o formulario interno. | Cadastro/edicao e registro de eventos quebram. | Pendente |
| A03 | A ocultacao de `.so-linux` depende da inicializacao interrompida. | Controles Linux continuam visiveis no Windows. | Pendente |
| A04 | Banner ficou em `PRONTO` com inicializacao interrompida. | Texto inicial pode parecer status atualizado. | Pendente |
| A05 | JS/CSS servidos coincidem com arquivos atuais; rotas existentes no codigo retornam 404. | Forte indicio de backend em execucao anterior as alteracoes atuais; nao foi reiniciado para confirmar. | Pendente |
| A06 | GET `/api/integracoes` retorna 404; card observado em `carregando...`. | Saude das integracoes indisponivel. | Pendente |
| A07 | GET `/api/pregacoes` retorna 404. | Programacao indisponivel nessa instancia. | Pendente |
| A08 | GET `/api/importacao/modelo` retorna 404. | Download do modelo indisponivel nessa instancia. | Pendente |
| A09 | API informa NotebookLM em `auth`, com dois estudos aguardando. | Processamento pausado por autenticacao. | Pendente |
| A10 | Formulario externo e encerrado antecipadamente pelo HTML invalido. | Campos posteriores deixam de pertencer ao formulario usado para salvar. | Pendente |

Referencias: `web/templates/index.html`, `web/static/app.js`, `app/api/routes.py`. Reiniciar o backend nao corrige o HTML invalido.

## B. Residuos de Raspberry/Linux no produto Windows

| ID | Recurso/artefato encontrado | Local principal | Decisao |
|---|---|---|---|
| B01 | Ethernet: status, IP e gateway pela implementacao Linux. | HTML, JS, `app/network/` | Retirada solicitada |
| B02 | Wi-Fi: procurar, conectar, desconectar, esquecer e senha. | HTML, JS, APIs de rede | Retirada solicitada |
| B03 | Access Point: rede `PREGACAO-PI-*`, IP, ativacao/desativacao e recuperacao. | HTML, JS, `nm.py`, `watchdog.py` | Retirada solicitada |
| B04 | Tailscale: status, autenticar, testar e endereco remoto. | HTML, JS, `tailscale.py` | Retirada solicitada |
| B05 | NetworkManager/nmcli; logs registram ferramenta ausente no Windows. | `app/network/nm.py` | Retirada solicitada |
| B06 | Rotas Wi-Fi/AP/Tailscale continuam registradas. | `app/api/network_routes.py`, `routes.py` | Retirada solicitada |
| B07 | Watchdog que gerencia rede e AP. | `app/network/watchdog.py` | Retirada solicitada |
| B08 | Comandos MQTT `WIFI_SCAN` e `WIFI_CONNECT`. | `app/remote/agent.py` | Retirada solicitada |
| B09 | Descoberta de armazenamento por `/proc/mounts`, `/dev/disk/by-label`, `/mnt` e `/media`. | `app/storage/destinos.py` | Substituir pela abordagem Windows |
| B10 | Rotulos e mensagens de cartao SD/SSD do Raspberry. | `destinos.py`, JS e documentacao | Retirada solicitada |
| B11 | Ausencia de enumeracao equivalente dos discos Windows; montagens retorna lista vazia. | `destinos.py` | Pendente |
| B12 | Backend ALSA/arecord junto do DirectShow; preferencia pela ferramenta encontrada. | `app/audio/device.py`, `recorder.py` | Revisar para Windows |
| B13 | Home padrao `/opt/pregacao-recorder` sem variavel de ambiente. | `app/paths.py` | Revisar para Windows |
| B14 | CLI com systemctl, sudo, ALSA e referencias ao Raspberry. | `app/cli.py` | Retirada/adaptacao solicitada |
| B15 | Servicos recorder, remote e netwatch do systemd. | `systemd/` | Retirada solicitada |
| B16 | Polkit, sudoers e Avahi. | `system/` | Retirada solicitada |
| B17 | Instalacao, atualizacao, desinstalacao e configuracao Linux/USB. | Scripts `.sh`, `scripts/` | Retirada solicitada |
| B18 | Exemplos de configuracao e instrucoes de AP/Linux. | `.env.example`, configuracao padrao | Retirada solicitada |
| B19 | Manuais/checklist ainda voltados ao Raspberry. | README, CHECKLIST, INSTALACAO-RASPBERRY, docs/REDE | Reescrever/retirar |
| B20 | Contexto antigo trata Raspberry/Kotlin como decisoes atuais. | `CONTEXTO.md` | Substituir contexto obsoleto |

Preservar conceitos uteis ao Windows: conectividade com internet, recuperacao de gravacao, armazenamento local, fila de upload e controle MQTT. Retirar Raspberry nao significa retirar esses conceitos.

## C. Funcionalidades incompletas ou com promessa maior que a implementacao

| ID | Item | Evidencia/limite | Decisao |
|---|---|---|---|
| C01 | Cadastro/edicao de pregacoes no celular. | Existem modelos Dart, mas nao tela nem integracao no controlador. | Pendente |
| C02 | Comandos MQTT de pregacoes. | Enum Flutter existe; agente nao aceita/executa os comandos. | Pendente |
| C03 | Metadados no estudo. | Snapshot pode ir ao banco, mas nao e passado ao pipeline. | Pendente |
| C04 | Metadados no PDF. | Snapshot nao identifica o documento gerado. | Pendente |
| C05 | Associar programacao e gravacao. | Busca igualdade exata de data/minuto, sem selecao explicita ao iniciar. Atraso pode impedir associacao. | Pendente |
| C06 | Snapshot imutavel. | Montado na execucao do estudo e pode ser recalculado; nao necessariamente congelado na gravacao. | Pendente |
| C07 | Retomar pela etapa pendente. | Job persiste, mas pipeline e chamado do inicio; nao ha checkpoints individuais. | Pendente |
| C08 | Nao repetir etapas. | Nova execucao cria novo notebook/relatorio; garantia documental nao esta assegurada. | Pendente |
| C09 | Repetir somente envio WhatsApp. | Falta fluxo persistente para reenviar apenas PDF. | Pendente |
| C10 | Evitar WhatsApp duplicado. | Falta persistencia do ID da mensagem para resolver falhas ambiguas/reinicio. | Pendente |
| C11 | Intervencao especifica em falha WhatsApp. | Falha encerra pipeline/job como erro. | Pendente |
| C12 | Retomar upload apos reinicio. | Upload e resumivel no processo, mas sessao nao persiste. | Pendente |
| C13 | Evitar duplicacao de upload em falha ambigua. | Arquivo pode chegar ao Drive e confirmacao falhar; retry cria outro. | Pendente |
| C14 | Estado principal de espera por intervencao. | Informacao depende em parte do detalhe textual; estado existe nos jobs, nao na maquina principal. | Pendente |
| C15 | Descartar progresso antigo no Flutter. | Recebimento do topico jobs nao compara `seq`. | Pendente |
| C16 | Gerenciamento individual de jobs na interface. | Falta painel completo de selecao, cancelamento e retentativa por job. | Pendente |

Referencias: `app/estudos.py`, `app/db.py`, `app/remote/agent.py`, `app/upload/drive.py`, `flutter/pregacao_controle/lib/` e pipeline externo. Persistencia de job nao equivale a persistencia de cada etapa.

## D. Defeitos e riscos adicionais

| ID | Achado | Tipo de evidencia | Decisao |
|---|---|---|---|
| D01 | Banco aceita data vazia, horario invalido e campos obrigatorios vazios. Rotas nao validam adequadamente esses campos. | Reproducao isolada e codigo | Pendente |
| D02 | Confirmacao de importacao confia nos itens enviados pelo cliente, sem repetir validacao da previa. | Codigo | Pendente |
| D03 | Importacao pode persistir parcialmente antes de falhar por duplicata. | Reproducao isolada | Pendente |
| D04 | Versao do cliente nao e exigida; edicao antiga pode sobrescrever mais recente. | Reproducao isolada e codigo | Pendente |
| D05 | Atualizacao parcial monta campos ausentes com `None`. | Codigo | Pendente |
| D06 | Duplicata na edicao nao recebe tratamento equivalente ao cadastro. | Codigo; risco de erro interno | Pendente |
| D07 | Interface aceita `.xls`, mas leitor usa openpyxl para `.xlsx`. | Codigo | Pendente |
| D08 | openpyxl instalado localmente, ausente do requirements do gravador. | Ambiente e manifesto | Pendente |
| D09 | Desmarcar manter copia local pode apagar MP3 ainda necessario ao estudo. | Codigo; opcao atual mantem copia | Pendente |
| D10 | Retencao apaga por idade sem consultar uploads/jobs pendentes. | Codigo; retencao atual desativada | Pendente |
| D11 | Configuracao altera valores em memoria antes de terminar validacao; erro nao desfaz anteriores. | Codigo | Pendente |
| D12 | Saude EMQX usa chamadas HTTP locais do agente como indicador. | Nao comprova conexao com broker | Pendente |
| D13 | Saude WhatsApp usa ultimo job, sem verificar sessao atual. | Pode confundir falha anterior ao envio com falha WhatsApp | Pendente |
| D14 | Detalhes de integracoes e data/horario concatenados em innerHTML sem escape. | Codigo; nao explorado | Pendente |
| D15 | Instancia atual retorna acesso admin sem PIN. | GET `/api/me`; nao implica exposicao externa comprovada | Pendente |
| D16 | BATs abrem consoles minimizados. | Execucao silenciosa e parcial | Pendente |

Referencias: `app/api/routes.py`, `app/importacao.py`, `app/db.py`, `app/upload/queue.py`, `app/storage/layout.py`, `web/static/app.js`, `iniciar-*.bat`.

## E. Base implementada que merece ser preservada

Estes itens possuem implementacao e cobertura ou estado registrado favoravel. Nao foram todos revalidados em hardware nesta auditoria.

| ID | Recurso | Evidencia/limite | Decisao |
|---|---|---|---|
| E01 | Captura Windows FFmpeg/DirectShow. | Codigo e testes; sem nova gravacao real. | Pendente |
| E02 | Gravacao segmentada e recuperacao. | Codigo e testes. | Pendente |
| E03 | Verificacao da consolidacao antes de remover segmentos. | Codigo e testes. | Pendente |
| E04 | Maquina de estados contra gravacoes simultaneas. | Codigo e testes. | Pendente |
| E05 | Fila persistente de upload, retry e verificacao tamanho/MD5. | Codigo/testes; servidor registra 12 uploads concluidos e zero pendentes. | Pendente |
| E06 | Jobs persistentes, guards de transicao e deduplicacao por caminho. | Codigo e testes; limites em C07/C08. | Pendente |
| E07 | Deteccao de autenticacao NotebookLM e espera preservando job. | Codigo/testes e dois jobs em espera observados. | Pendente |
| E08 | Gravacao independente do controle remoto. | Separacao arquitetural. | Pendente |
| E09 | MQTT TLS, ACK, reconexao e estado retido. | Implementacao e testes; sem novo E2E nesta auditoria. | Pendente |
| E10 | Base de progresso web/Flutter. | Implementada; painel bloqueado por A01 e limite C15. | Pendente |
| E11 | Suite Python. | 342 testes verdes em copia isolada; nao cobre falha real do DOM. | Pendente |
| E12 | Drive configurado/conectado. | Estado reportado pela instancia; sem novo upload. | Pendente |

## F. Documentacao, distribuicao e excesso de artefatos

| ID | Achado | Decisao |
|---|---|---|
| F01 | SPRINTS marca formulario APK como concluido, mas existem apenas modelos sem fluxo completo. | Pendente |
| F02 | README promete retomada sem repetir etapas, alem do implementado. | Pendente |
| F03 | Contagens de testes divergem entre documentos; auditoria atual executou 342. | Pendente |
| F04 | Documentacao cita Flutter 2.5; pubspec atual e 2.6.0+12. | Pendente |
| F05 | Projeto Kotlin legado, APK 2.5 na raiz e Flutter atual coexistem. | Pendente |
| F06 | CONTEXTO.md antigo contem credenciais; nao copiar/distribuir como documento geral. Nenhum valor foi incluido aqui. | Pendente |
| F07 | Provas reais de dois celulares/reconexao, reinicio durante processamento e E2E completo seguem pendentes no plano. | Pendente |
| F08 | Manual operador/PDF com capturas reais, documentacao tecnica atualizada, conjunto de fluxogramas e relatorio final nao estao todos concluidos. | Pendente |
| F09 | Pipeline depende de pasta externa ao repositorio principal. Instalacao e versao do produto ficam fragmentadas. | Pendente |
| F10 | Fluxo completo nao e obrigatoriamente sequencial como o diagrama sugere: estudo e upload sao disparados em paralelo. | Pendente |

Pipeline configurado na auditoria: `C:\Users\Aska\Documents\Default Project\sermon-pipeline`. Foram lidos `pipeline.py` e `whatsapp/send.js` sem executar processamento ou envio.

## G. Decisoes de produto a preencher antes da implementacao

- [ ] Confirmar quais itens A/D corrigir primeiro.
- [ ] Revisar retirada dos itens B, preservando controle remoto Windows.
- [ ] Definir se programacao de pregacoes permanece.
- [ ] Definir se importacao CSV/XLSX permanece.
- [ ] Se programacao permanecer, definir cadastro no PC, celular ou ambos.
- [ ] Definir se metadados devem aparecer no estudo e PDF.
- [ ] Definir politica de retencao e copia local sem prejudicar jobs pendentes.
- [ ] Definir uso de PIN no PC e acesso pela rede local.
- [ ] Definir inicializacao Windows inteiramente sem console.
- [ ] Definir consolidacao do gravador e pipeline na instalacao/distribuicao.
- [ ] Escolher uma unica versao oficial do aplicativo e destino dos legados.
- [ ] Separar status simples do operador e diagnosticos tecnicos do administrador.

## Proximo passo recomendado

Atualizar a pagina e usar RENOVAR LOGIN para concluir a entrada na conta Google no PC. Conferir a sessao confirmada e a retomada dos estudos preservados. Depois, revisar os itens C/D pendentes pelos IDs. Estado atual em docs/CODEX_CONTEXT.md; retirada em docs/REMOCAO_RASPBERRY.md.

Nao reiniciar servicos, apagar legados, alterar credenciais, renovar login ou executar correcoes apenas por ler este documento. Consultar o codigo e o estado atual antes de implementar, pois esta auditoria representa o momento indicado no inicio.
