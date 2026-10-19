# Como funciona o Pregacao Recorder

O PC Windows recebe o audio da mesa, grava localmente e mostra o estado no painel.
O aplicativo no celular controla o PC pela internet; nao captura nem processa audio.

## Caminho do audio

1. A interface USB/DirectShow entrega audio ao FFmpeg.
2. O gravador preserva segmentos WAV para recuperacao em interrupcoes.
3. Ao finalizar, consolida e verifica o MP3.
4. A fila do Drive envia o arquivo e confirma integridade.
5. Em paralelo, a fila de estudos aciona um pipeline externo.
6. NotebookLM gera o estudo, convertido em PDF e enviado pelo WhatsApp.

## Operacao

Abrir `iniciar-tudo.bat` e `http://127.0.0.1:8080`. Conferir audio/disco, iniciar,
finalizar e ouvir o arquivo. A rede do PC e configurada no Windows.
Sem internet a gravacao continua e uploads aguardam. Disco indisponivel impede
nova captura; o destino nao e substituido automaticamente.

## Limites

Autenticacao do NotebookLM pode expirar. Jobs sao preservados, mas a retomada do
pipeline ainda pode repetir etapas. Envio WhatsApp nao comprova leitura/entrega
final. Metadados do cadastro ainda nao entram no PDF. Provas com hardware real
seguem o checklist, separadas de testes automatizados.

Detalhes: `GUIA-USUARIO.md`, `docs/WINDOWS.md`, `docs/TESTES.md` e auditoria.
