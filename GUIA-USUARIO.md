# Manual do operador - Windows

## Gravar

1. Conectar a mesa/interface de audio e abrir `iniciar-tudo.bat`.
2. Aguardar o painel abrir no navegador e informar PIN se solicitado.
3. Conferir interface de audio e espaco livre.
4. INICIAR GRAVACAO; acompanhar estado e cronometro.
5. FINALIZAR GRAVACAO e confirmar. Aguardar consolidacao.
6. Conferir o arquivo no HISTORICO e ouvir o audio.

O mesmo iniciador abre gravador e controle remoto, sem janelas extras. Para abrir
o painel manualmente, usar `http://127.0.0.1:8080` (porta padrao). Se houver erro
ao iniciar, a janela mostra a orientacao e aguarda uma tecla; consultar
[operacao Windows](docs/WINDOWS.md) para diagnostico e logs.

Sem internet, a captura permanece local e o upload aguarda.
Disco ausente ou sem permissao impede nova gravacao; reconectar ou escolher pasta.
O sistema nao muda automaticamente o destino para outro disco.

## Celular

Configurar o aplicativo com broker, identificador e token de operador definidos
pelo administrador. O celular envia comandos e recebe o estado do PC; ele nao grava
nem altera o Wi-Fi do computador. Internet do PC/celular e necessaria para MQTT.

## Estudo

Se habilitado, o estudo entra em fila apos consolidar o audio. NotebookLM pode
pedir renovacao de login pelo PC. O PDF/WhatsApp depende de um pipeline externo.
Falhas de envio e retomada individual de etapas continuam com limitacoes.
Nao considerar 100% da barra uma prova de entrega lida pelo destinatario.

## Configurar

CONFIG concentra Google Drive e estudo automatico. CONFIGURACOES AVANCADAS reune
audio, armazenamento e diagnosticos. A rede do PC e configurada pelo Windows.
Se houver GRAVACAO INTERROMPIDA, seguir `docs/RECUPERACAO.md`.
Nao apagar pastas, tokens nem banco para resolver um erro de interface.
