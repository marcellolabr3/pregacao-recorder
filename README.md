# Pregacao Recorder

Gravador de pregacoes para Windows com painel local e controle Android por MQTT/TLS.

## Comecar

1. Seguir [instalacao Windows](docs/WINDOWS.md).
2. O laboratorio esta registrado para iniciar com o Windows. Para abrir
   manualmente, executar `iniciar-tudo.bat` nesta copia de desenvolvimento.
3. Aguardar o painel abrir no navegador (`http://127.0.0.1:8080` por padrao).
4. Configurar audio, pasta de gravacao e Google Drive pelo painel.

O iniciador verifica os requisitos e abre gravador e agente MQTT em processos
separados, sem janelas extras. Para conferir a instalacao sem iniciar os servicos,
executar `iniciar-tudo.bat --verificar`. Opcoes e logs: [operacao Windows](docs/WINDOWS.md).

## Uso da interface

CONFIG agora separa **Equipamento**, **Google e estudos**, **WhatsApp**,
**Automacao**, **Aparencia** e **Avancado**. Cada aba salva somente os seus
campos. A programacao na tela principal usa **NOVA PREGACAO** para inclusao
manual; o antigo modelo/importador deixou de aparecer no painel. Icone e imagem
de fundo podem ser escolhidos localmente no painel e no celular.

Durante **GRAVANDO**, **DESCARTAR GRAVACAO** pede confirmacao e elimina a captura
sem consolidar MP3, enfileirar upload ou gerar estudo. **FINALIZAR GRAVACAO**
continua o fluxo normal. A barra do estudo avanca do dourado ao verde; se uma
etapa falhar, mostra vermelho e identifica a etapa. Detalhes no
[manual do operador](GUIA-USUARIO.md).

## Instalacao completa no novo PC

O instalador completo anterior, `PregacaoRecorder-Completo-Instalar-local-20261021T024329576035Z.exe`,
leva programa, runtimes, contas, banco, estudos e gravacoes da edicao pessoal
para `%LOCALAPPDATA%\PregacaoRecorder-Pessoal` no novo PC. Essa copia funciona
sem o SSD e registra o inicio automatico para o usuario Windows local. Leia
`INSTALAR-NO-OUTRO-PC.txt` na raiz e o [guia local](docs/GUIA_INSTALACAO_LOCAL.md).
O instalador publico sem dados foi preservado em `Pacote-Publico-Sem-Dados`.
Esse instalador foi montado antes da reorganizacao de CONFIG e ainda precisa
ser atualizado a partir do SSD pessoal atual para incluir esta interface.
O pacote Windows atualizado esta em
`dist-pacote/PregacaoRecorder-release-20261021T115915854351Z` e o atualizador
pessoal pronto em
`dist-pacote/PregacaoRecorder-Pessoal-Atualizar-update-20261021T120614Z.exe`.
O atualizador foi compilado, mas nao aplicado: a unidade `E:` acessivel agora
esta vazia e nao contem `PregacaoRecorder-Pessoal`. Uma versao de prova do
instalador completo 2.8 foi montada a partir da copia pessoal verificada de
20/10/2026. Ela tem 583 MB, inclui o APK 2.8, 16 gravacoes e as contas dessa
copia. Foi colocada na `E:` com o nome `snapshot-20261020`, deixando explicita
a data da origem; nao foi confirmado se houve novas gravacoes ou alteracoes de
conta depois dela. O montador agora inclui
somente os dados ativos e descarta backups, logs, caches e arquivos de teste;
na unidade de entrega ha apenas o `.exe` e seu `.exe.sha256`.

A pasta `PregacaoRecorder-Pessoal`, quando estiver acessivel no SSD original,
continua sendo a copia portatil e um backup. Nao inicie as duas copias ao
mesmo tempo: elas conservam a mesma
identidade MQTT. Alteracoes feitas em uma nao sao sincronizadas automaticamente
com a outra. O laboratorio usa identidade MQTT propria (`pregacao-lab-aska`).
No PC de destino, confira audio, contas e dois celulares conforme o
[guia do SSD](docs/GUIA_SSD_PORTATIL.md) e o
[roteiro de aceite](docs/ACEITE_WINDOWS.md).

## APK Android 2.8

O novo aplicativo para os dois celulares e
`dist-pacote/PregacaoControle-2.8.apk`, versao
`2.8.0+14`. SHA-256:
`CC3D4E3DBC3E1F3A2AF4F592C98F975330A22E60DE574CAB9FB7FD20F3779CC2`.
O APK e um artefato local de build, ignorado pelo Git; o repositorio contem
o codigo-fonte e as instrucoes para recompilar.
`apksigner` validou o APK e confirmou o mesmo certificado da versao anterior;
atualize por cima do aplicativo instalado para preservar a configuracao.
O APK traz descarte da gravacao, barra dourada ate verde, indicacao vermelha de
falha, tela escura e imagens configuraveis. O icone de fabrica e preto/dourado;
uma foto escolhida pelo usuario pode ser usada em um atalho da tela inicial.

Instale ou atualize o APK manualmente em **cada celular**; o instalador Windows
nao instala aplicativos Android. O app nao pede PIN, mas a conexao MQTT
conserva senha e token. O instalador datado colocado na `E:` inclui o APK 2.8;
o instalador completo anterior ainda inclui o APK 2.7.
O SSD pessoal com os dados mais recentes ainda nao estava disponivel nesta
etapa. O usuario relatou que o teste funcional anterior foi bem-sucedido; a
instalacao do APK 2.8 nos dois celulares e sua prova real com o novo PC ainda
precisam ser conferidas.

## Fluxo implementado

```text
Mesa/microfone -> FFmpeg/DirectShow -> segmentos WAV -> MP3 local
                                                    |-> fila Google Drive
                                                    |-> fila de estudos -> pipeline externo
                                                                          NotebookLM -> PDF -> WhatsApp
```

O audio continua local sem internet. Upload e estudo usam filas separadas e podem
processar em paralelo. O celular envia comandos e permite manter a programacao;
o PC grava e processa. Tarefas concluidas mostram 100%, inclusive quando
etapas opcionais sao puladas e identificadas como tal.

Em **CONFIG**, informe um ou mais numeros com DDI e DDD (um por linha), salve e
confira **DESTINOS SALVOS**. Conecte o WhatsApp pelo QR no proprio painel e use
**VERIFICAR CONEXAO** neste computador. A sessao e local a cada instalacao;
sem ela, o PDF nao e enviado. O sistema distingue tentativa, aceite pelo servidor
e falha. Aceite pelo servidor ainda nao comprova entrega no telefone. Um estudo
pronto pode ser reenviado a outros numeros pelo painel, usando o PDF existente.

O mapa mental e opcional: marque a caixa em CONFIG e escreva as instrucoes no
campo proprio. O NotebookLM gera um mapa do mesmo estudo; o painel permite
visualizar a arvore e baixar seu JSON. O desligamento automatico do Windows
tambem e opcional e vem desligado: defina o atraso em CONFIG, salve e arme a
tarefa. Gravacao, uploads, estudos ou reenvios pendentes adiam a contagem.

## Componentes

- `app/`: Flask/waitress, SQLite, captura, recuperacao, upload, estudos e agente MQTT.
- `web/`: painel de gravacao, historico e configuracoes.
- `flutter/pregacao_controle/`: aplicativo atual; `android/` e fonte Kotlin legada.
- `scripts/pregacao.cmd`: diagnostico Windows (`status`, `doctor`, `logs`).
- `tests/`: testes Python; usar ambiente isolado conforme `docs/TESTES.md`.
- Pipeline externo configurado em `estudos.python` e `estudos.pasta` no config local.

## Limites atuais

- Autenticacao do NotebookLM pode exigir login; jobs ficam em espera.
- Jobs persistem, mas o pipeline ainda nao retoma cada etapa individualmente.
- Upload apos reinicio nao persiste a sessao resumivel; falhas ambiguas podem duplicar arquivos.
- WhatsApp nao comprova entrega final; antes de reenviar, confira o telefone
  para evitar duplicatas se o resultado anterior ficou incerto.
- O mapa mental e salvo em JSON; exportacao em imagem/PDF nao foi implementada.
- Metadados da gravacao ainda nao sao enviados ao pipeline; o formulario Flutter
  de gravacao continua incompleto.
- Provas com audio real, dois celulares e reinicio no meio do pipeline continuam pendentes.

## Documentacao

[Manual](GUIA-USUARIO.md) | [Arquitetura](DOCUMENTACAO.md) |
[Drive](docs/GOOGLE_DRIVE.md) | [MQTT](docs/AGENTE.md) |
[Plano de retirada](docs/REMOCAO_RASPBERRY.md) |
[Auditoria revisavel](CONTEXTO_AUDITORIA_PRODUTO.md) |
[Contexto operacional](docs/CODEX_CONTEXT.md).

Credenciais e dados locais sao ignorados pelo Git. Nao distribuir `.env`, tokens,
banco, logs ou o contexto local antigo com credenciais.
