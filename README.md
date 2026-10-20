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

## Edicao pessoal no SSD

No SSD, use `PregacaoRecorder-Pessoal\Iniciar Pregacao.cmd` sob a letra atribuida
pelo Windows. `Verificar Pacote.cmd` confere as dependencias. O SSD esta no
outro PC; o usuario informou que abriu o programa e entrou no NotebookLM la.
A revisao 2.7.0+13 do APK e o atualizador da pasta pessoal estao em preparacao.
O atualizador preserva contas, banco, gravacoes e o login feito no outro PC.
O laboratorio usa identidade MQTT propria (`pregacao-lab-aska`); a instalacao
pessoal conserva a identidade real. Ao usar o SSD, confira audio, conexao dos
dois celulares e contas conforme o [guia do SSD](docs/GUIA_SSD_PORTATIL.md)
e o [roteiro de aceite](docs/ACEITE_WINDOWS.md). A pasta antiga do SSD sera
conferida e eliminada quando essa unidade estiver acessivel.

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
- WhatsApp nao comprova entrega final; retry individual/idempotente permanece pendente.
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
