# Internet e acesso ao painel

Ethernet e Wi-Fi sao administrados pelas configuracoes do Windows.
O gravador mostra apenas a disponibilidade de internet para as integracoes.
Nao configura interfaces, hotspot ou VPN.

- No PC: `http://127.0.0.1:8080`.
- Rede local: endereco IP do PC e porta configurada, se `PREGACAO_HOST=0.0.0.0`
  e firewall permitir. Com `127.0.0.1`, somente o proprio PC acessa.
- Fora da rede local: aplicativo Android via MQTT/TLS, sem expor a porta do painel.

A captura local independe da internet. Uploads aguardam e tentam novamente.
O teste TCP de conectividade nao comprova saude do Drive/NotebookLM/WhatsApp.
Configuracoes administrativas mantidas: destino do teste, porta e intervalo de retry.
Nao foram alteradas as regras de firewall nem a rede do Windows nesta retirada.
