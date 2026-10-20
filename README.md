# Pregacao Recorder

Gravador de pregacoes para Windows com painel local e controle Android por MQTT/TLS.

## Comecar

1. Seguir [instalacao Windows](docs/WINDOWS.md).
2. Executar `iniciar-tudo.bat` nesta copia de desenvolvimento.
3. Aguardar o painel abrir no navegador (`http://127.0.0.1:8080` por padrao).
4. Configurar audio, pasta de gravacao e Google Drive pelo painel.

O iniciador verifica os requisitos e abre gravador e agente MQTT em processos
separados, sem janelas extras. Para conferir a instalacao sem iniciar os servicos,
executar `iniciar-tudo.bat --verificar`. Opcoes e logs: [operacao Windows](docs/WINDOWS.md).

## Edicao pessoal no SSD

No SSD `E:`, a unica pasta visivel do produto e `PregacaoRecorder-Pessoal`.
Abra `E:\PregacaoRecorder-Pessoal\Iniciar Pregacao.cmd`; para conferir as
dependencias sem iniciar os servicos, use `Verificar Pacote.cmd` na mesma pasta.
O APK atual (`2.6.0+12`) tambem esta nela. A pasta funciona sem a instalacao
antiga e sem o instalador na raiz do SSD. Ao usar outro PC, confira audio,
conexao do celular e contas conforme o [guia do SSD](docs/GUIA_SSD_PORTATIL.md)
e o [roteiro de aceite](docs/ACEITE_WINDOWS.md). O login do NotebookLM precisa
ser renovado antes de gerar um novo estudo.

## Fluxo implementado

```text
Mesa/microfone -> FFmpeg/DirectShow -> segmentos WAV -> MP3 local
                                                    |-> fila Google Drive
                                                    |-> fila de estudos -> pipeline externo
                                                                          NotebookLM -> PDF -> WhatsApp
```

O audio continua local sem internet. Upload e estudo usam filas separadas e podem
processar em paralelo. O celular envia comandos e exibe o estado; o PC grava e processa.

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
- Metadados ainda nao sao enviados ao pipeline; formulario Flutter esta incompleto.
- Provas com audio real, dois celulares e reinicio no meio do pipeline continuam pendentes.

## Documentacao

[Manual](GUIA-USUARIO.md) | [Arquitetura](DOCUMENTACAO.md) |
[Drive](docs/GOOGLE_DRIVE.md) | [MQTT](docs/AGENTE.md) |
[Plano de retirada](docs/REMOCAO_RASPBERRY.md) |
[Auditoria revisavel](CONTEXTO_AUDITORIA_PRODUTO.md) |
[Contexto operacional](docs/CODEX_CONTEXT.md).

Credenciais e dados locais sao ignorados pelo Git. Nao distribuir `.env`, tokens,
banco, logs ou o contexto local antigo com credenciais.
