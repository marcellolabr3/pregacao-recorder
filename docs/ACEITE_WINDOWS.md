# Aceite da entrega pessoal no novo PC

Use `Gerador de Estudo.exe` e `Controle Android.apk` da entrega privada. Registre
somente resultado e erro observado; nunca senhas, tokens, cookies ou dados da conta.

- [ ] Instalar no Windows x64 sem ferramentas de desenvolvimento. Conferir que o
  atalho abre o painel e que o serviço aparece na bandeja após novo login.
- [ ] Conferir que a instalação começa sem banco antigo, gravações, backups,
  sessões do WhatsApp ou perfil do NotebookLM.
- [ ] Escolher a interface de áudio e a pasta do novo PC, testar sinal e salvar.
- [ ] Conferir que o broker MQTT e o mesmo ID do PC de origem estão presentes.
  Desligar o agente do PC antigo antes de testar o novo. Enviar STATUS pelo
  celular e verificar ACK real.
- [ ] Conferir o status da conta Google Drive já autorizada. Se o Google tiver
  revogado o token, reconectar a mesma conta pelo painel.
- [ ] Fazer uma gravação curta, finalizar, ouvir o MP3 e confirmar a pasta.
  Repetir sem login Google ou internet: a captura local deve funcionar; o envio
  automático deve aguardar conexão/autorização.
- [ ] Enviar um áudio de teste ao Drive e verificar o arquivo na conta correta.
- [ ] Se usados, entrar novamente no NotebookLM e no WhatsApp no novo PC.
- [ ] Atualizar o APK no celular, conferir estado, histórico e comandos MQTT.
- [ ] Reinstalar somente quando o serviço estiver ocioso. Conferir que os dados
  anteriores foram movidos para `<pasta>-dados-anteriores` e que a instalação
  nova começa vazia. Testar a desinstalação pelo menu Iniciar.

Os testes automatizados não comprovam captura na interface real nem acesso à
conta e ao broker no computador de destino. Esses itens dependem do teste acima.
