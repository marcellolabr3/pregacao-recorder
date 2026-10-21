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

## Instalacao completa no novo PC

Na raiz do SSD, `PregacaoRecorder-Completo-Instalar-local-20261021T024329576035Z.exe`
leva programa, runtimes, contas, banco, estudos e gravacoes da edicao pessoal
para `%LOCALAPPDATA%\PregacaoRecorder-Pessoal` no novo PC. Essa copia funciona
sem o SSD e registra o inicio automatico para o usuario Windows local. Leia
`INSTALAR-NO-OUTRO-PC.txt` na raiz e o [guia local](docs/GUIA_INSTALACAO_LOCAL.md).
O instalador publico sem dados foi preservado em `Pacote-Publico-Sem-Dados`.

A pasta `PregacaoRecorder-Pessoal` no SSD continua disponivel para uso portatil
e backup. Nao inicie as duas copias ao mesmo tempo: elas conservam a mesma
identidade MQTT. Alteracoes feitas em uma nao sao sincronizadas automaticamente
com a outra. O laboratorio usa identidade MQTT propria (`pregacao-lab-aska`).
No PC de destino, confira audio, contas e dois celulares conforme o
[guia do SSD](docs/GUIA_SSD_PORTATIL.md) e o
[roteiro de aceite](docs/ACEITE_WINDOWS.md).

## APK Android desta entrega

O aplicativo para os dois celulares e `PregacaoControle-2.7.apk`, versao
`2.7.0+13`. Ele esta na raiz do SSD (atualmente `E:\PregacaoControle-2.7.apk`),
na pasta `PregacaoRecorder-Pessoal` do SSD e no instalador completo para o PC.
As duas copias do SSD conferem pelo SHA-256
`CEC2A680D8738099F1FDEAA459B390B25D6F9789D2C6608922D0EEC1D889C0C1`.
O release foi assinado com a mesma chave do APK anterior, para atualizar o
aplicativo ja instalado sem apagar sua configuracao.

Instale ou atualize o APK manualmente em **cada celular**; o instalador Windows
nao instala aplicativos Android. Esta versao mostra a programacao na tela
inicial, o progresso concluido a 100% com etapas opcionais identificadas e a
distincao entre aceite pelo servidor e envio incerto do WhatsApp. O aplicativo
nao pede PIN, mas a conexao MQTT conserva senha e token. O ajuste do instalador
Windows de 21/10/2026 nao alterou o codigo Android nem exigiu outro APK.
A instalacao e o teste real nos dois celulares no novo PC ainda estao pendentes.

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
