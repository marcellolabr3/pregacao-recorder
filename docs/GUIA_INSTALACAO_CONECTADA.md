# Gerador de Estudo no novo PC — cópia pessoal

Este instalador leva sua configuração atual do broker MQTT e a autorização já
concedida à sua conta do Google Drive. Ele não leva gravações, banco de dados,
backups, cookies, perfis de navegador nem caminhos locais do PC antigo. Guarde
o instalador em local privado, pois ele contém credenciais da sua conta.

1. Instale `Gerador de Estudo.exe` no novo PC. O padrão é
   `%LOCALAPPDATA%\Gerador de Estudo`. O programa inicia com o Windows; o atalho
   abre o painel. Instale `Controle Android.apk` no celular.
2. Em **CONFIG > CONFIGURAÇÕES AVANÇADAS**, escolha a interface de áudio e
   **Onde gravar** no novo PC. Faça **TESTAR SINAL** e salve. O disco e o nome
   da interface podem ser diferentes dos usados no PC antigo.
3. Confira no painel o status do **Google Drive** e do **CONTROLE REMOTO**.
   A autorização do Drive foi copiada da origem; se o Google a
   revogar depois, use **CONECTAR CONTA GOOGLE**. Para testar o broker, envie
   **STATUS** pelo celular e confira o ACK.
4. Faça uma gravação curta, pare e confira o arquivo local e o envio. Gravar
   funciona mesmo sem login Google ou internet; nesse caso, se o envio
   automático estiver ativo, o arquivo fica na fila e o Drive tenta enviá-lo
   quando a conta e a conexão estiverem disponíveis.

Esta cópia preserva o ID MQTT usado pelo celular. Desligue o agente do PC antigo
antes de usar o novo, pois dois PCs com o mesmo ID podem derrubar a conexão um
do outro. A instalação começa com histórico novo. NotebookLM e WhatsApp usam
sessões separadas e exigem novo login se você for utilizá-los.

Para desinstalar, use **Desinstalar Gerador de Estudo** no menu Iniciar. Aguarde
as gravações e os envios terminarem. Fechar o navegador não encerra o serviço.
