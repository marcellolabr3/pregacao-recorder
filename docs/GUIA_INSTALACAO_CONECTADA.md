# Gerador de Estudo no novo PC — cópia pessoal

Copie os arquivos `Gerador de Estudo.exe` e `Controle Android.apk` da raiz de
`E:\`. Os arquivos `.sha256` ao lado deles permitem conferir as cópias.

O instalador leva a configuração atual do broker MQTT, a autorização renovável
do Google Drive e a sessão atual do NotebookLM. Se o login durável do
NotebookLM foi ativado antes do build, leva também o `master_token.json` para
recriar e renovar a sessão automaticamente. Quando já existe uma sessão
vinculada do WhatsApp, ela e os destinatários também são levados. O
`LEIA-ME.txt` informa quais sessões foram incluídas. O APK separado já vem com
a conexão MQTT do operador preenchida. A entrega não leva gravações, banco de
dados, backups nem caminhos locais do PC antigo. Guarde os dois arquivos em
local privado, pois contêm credenciais de acesso.

1. Instale `Gerador de Estudo.exe` no novo PC. O padrão é
   `%LOCALAPPDATA%\Gerador de Estudo`. O programa inicia com o Windows; o atalho
   abre o painel. Instale `Controle Android.apk` no celular.
2. Em **CONFIG > CONFIGURAÇÕES AVANÇADAS**, escolha a interface de áudio e
   **Onde gravar** no novo PC. Faça **TESTAR SINAL** e salve. O disco e o nome
   da interface podem ser diferentes dos usados no PC antigo.
3. Confira no painel o status do **Google Drive**, **NotebookLM**, **WhatsApp**
   e **CONTROLE REMOTO**. No celular, use **DIAGNOSTICAR SESSAO** para verificar
   e tentar renovar a conta NotebookLM. **RENOVAR LOGIN NO PC** abre a entrada
   no navegador do computador caso a sessão não possa ser recuperada.
   A autorização do Drive foi copiada da origem; se o Google a
   revogar depois, use **CONECTAR CONTA GOOGLE**. Para testar o broker, envie
   **STATUS** pelo celular e confira o ACK.
4. Faça uma gravação curta, pare e confira o arquivo local e o envio. Gravar
   funciona mesmo sem login Google ou internet; nesse caso, se o envio
   automático estiver ativo, o arquivo fica na fila e o Drive tenta enviá-lo
   quando a conta e a conexão estiverem disponíveis.

Esta cópia preserva o ID MQTT usado pelo celular. Desligue o agente do PC antigo
antes de usar o novo, pois dois PCs com o mesmo ID podem derrubar a conexão um
do outro. Também use o NotebookLM em um PC por vez para evitar sessões que se
invalidem. A instalação começa com histórico novo. Sem o token durável, a sessão
NotebookLM copiada pode expirar e exigir novo login. A sessão WhatsApp copiada
pode exigir novo QR caso o serviço a revogue.

Para desinstalar, use **Desinstalar Gerador de Estudo** no menu Iniciar. Aguarde
as gravações e os envios terminarem. Fechar o navegador não encerra o serviço.
