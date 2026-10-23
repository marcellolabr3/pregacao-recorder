# Gerador de Estudo no outro PC — edição pública

Este guia descreve o instalador sem credenciais. Para a entrega pessoal que
preserva broker MQTT e autorização Google Drive, use
[GUIA_INSTALACAO_CONECTADA.md](GUIA_INSTALACAO_CONECTADA.md).

Windows 10/11 de 64 bits. O pacote inclui Python, Node, FFmpeg e navegador;
instale o driver da interface de audio caso o Windows ainda nao a reconheca.

## Instalar e abrir

1. Copie `Gerador de Estudo.exe` para o PC e execute-o. Escolha a pasta de
   instalacao; o padrao e `%LOCALAPPDATA%\Gerador de Estudo`.
2. O servico inicia com o Windows e aparece na bandeja. O atalho
   **Gerador de Estudo** abre somente o painel no navegador, na porta 8080 por
   padrao. Na bandeja, dourado indica painel ativo e vermelho, indisponivel.
3. Na primeira abertura o pacote prepara os caminhos do pipeline, um segredo
   local de sessao e um ID exclusivo do equipamento. Nao e preciso editar caminhos.
4. Para conferir o pacote sem iniciar captura, filas ou conexoes, execute
   **Verificar Pacote.cmd** na pasta instalada. Avisos de contas ausentes sao
   esperados antes de configurar as integracoes.

`Controle Android.apk` e um arquivo separado, ao lado do instalador Windows.
Instale ou atualize o aplicativo em cada celular diretamente com esse APK; nao
e necessario instalar o programa Windows para obter o arquivo Android.

Para desinstalar, use **Desinstalar Gerador de Estudo** no menu Iniciar ou
**Configuracoes > Aplicativos**. Aguarde terminar gravacoes, uploads, estudos e
envios; o desinstalador encerra os servicos desta instalacao quando estiverem
ociosos. Fechar o navegador nao encerra os servicos. A desinstalacao preserva
os dados criados pelo uso. Uma reinstalacao na mesma pasta move configuracao,
banco, sessoes e gravacoes para `<pasta>-dados-anteriores\DATA-HORA` e inicia
vazia. Os audios sao movidos, sem duplicacao. Confira essa pasta antes de
apagar dados antigos.

## Audio e pasta

Abra **CONFIG > CONFIGURACOES AVANCADAS**, informe seu PIN administrativo se
solicitado, escolha o dispositivo de captura e **Onde gravar**, e salve.
Use **TESTAR SINAL** junto ao seletor para testar a interface selecionada antes
de salvar. O teste nao troca a configuracao de gravacao. Salve, saia da tela e
abra novamente para conferir dispositivo, canais, taxa e pasta escolhidos.
Confirme espaco livre no destino.
A gravacao local funciona sem internet; as integracoes aguardam conectividade.

Uma instalacao nova inicia com historico novo. O instalador nao transfere o
banco, gravacoes, credenciais nem copias locais do PC de origem. Os arquivos
ja enviados ao Google Drive continuam na nuvem. Reescolha interface e disco
no destino, pois os nomes e letras das unidades podem mudar.

## Contas e estudo

1. **Drive:** em CONFIGURACOES AVANCADAS, informe as mesmas credenciais OAuth
   privadas do usuario e a pasta de destino. Em CONFIG, use **CONECTAR CONTA
   GOOGLE** e autorize a conta. Se o retorno OAuth usa `localhost`, abra o painel
   por `http://localhost:8080`. **TESTAR CONEXAO/PASTA** acessam a conta real.
2. **NotebookLM:** em CONFIG, use **RENOVAR LOGIN** e conclua o login no navegador
   aberto no proprio PC. Depois use **DIAGNOSTICAR SESSAO**. Essa sessao e
   separada da autorizacao do Drive; aguarde finalizar antes de iniciar estudos.
3. **WhatsApp:** em CONFIG, informe os numeros com DDI e DDD (um por linha),
   salve e confira **DESTINOS SALVOS**. Clique **CONECTAR WHATSAPP (QR)**. No
   telefone use **Aparelhos conectados > Conectar aparelho** e leia o QR
   exibido no painel. Clique **VERIFICAR CONEXAO** antes de gerar estudos.
   **Conectar WhatsApp.cmd** continua disponivel como alternativa local. Cada
   instalacao tem sua propria sessao; no PC novo, conecte novamente. Nao copie
   cookies/perfis nem `whatsapp/auth` do PC anterior.
4. **Mapa mental:** marque **Gerar tambem um mapa mental** e escreva as
   instrucoes no campo em CONFIG. Apos o estudo, selecione-o em CONFIG para
   visualizar a arvore e baixar o arquivo JSON.
5. **Desligamento:** a opcao vem desativada. Em CONFIG, marque o desligamento,
   escolha o atraso em minutos e salve. O monitor espera gravacao, uploads,
   estudos e reenvios terminarem. **ARMAR PARA AS TAREFAS ATUAIS** inicia a
   contagem mesmo se o PC ja estiver ocioso; **CANCELAR CONTAGEM** cancela o
   ciclo atual. Uma nova tarefa reinicia o prazo.

As filas atuais fazem upload e estudo separadamente. **Aceito pelo servidor**
significa que o WhatsApp devolveu um ID de mensagem, sem confirmar a entrega
ao telefone. O painel permite reenviar o PDF pronto a outros numeros sem
recriar o estudo. Confira o recebimento antes de repetir um envio incerto.

## PINs e configuracao privada

PINs continuam em `gravador\.env`, dentro da pasta instalada. A conexao MQTT
pode ser configurada em **CONFIG > CONFIGURACOES AVANCADAS > CONTROLE REMOTO**.
O primeiro uso gera `PREGACAO_SECRET` se estiver ausente/vazio; nao troque esse
segredo ao reabrir ou atualizar. O pacote generico nao leva suas credenciais.

Se quiser manter os PINs, copie privadamente somente os valores
`PREGACAO_PIN` e `PREGACAO_ADMIN_PIN` para esse `.env`, preservando o segredo
local gerado. O PIN administrativo vazio usa o PIN comum. Para o controle remoto,
informe no cartao administrativo o servidor, porta, TLS, usuario/senha do PC,
ID do equipamento e token do operador. Use os dados privados do seu broker.
Senha e token em branco ao salvar preservam os valores anteriores.
Credenciais do PC e do operador sao separadas; mantenha TLS quando usado pelo broker.

Use `gravador\.env.example` como referencia. Nao substitua o `.env` inteiro por
uma copia antiga: caminhos, porta e identidade antigos podem apontar ao outro
PC. A configuracao MQTT salva pelo painel prevalece sobre os campos MQTT legados
do `.env`. Nao copie tokens OAuth, perfis do navegador, banco, logs ou QRs como
parte da configuracao. Depois de salvar MQTT ou mudar o `.env`, aguarde concluir
gravacoes, uploads, estudos e logins e reinicie o Windows; depois abra o atalho.
Fechar somente a aba do navegador nao encerra os servicos nem aplica o reinicio.

## Celular e MQTT: dois PCs ou substituicao

**Dois PCs podem funcionar:** mantenha o novo ID gerado. Consulte o cartao
**CONTROLE REMOTO**, em **CONFIG > CONFIGURACOES AVANCADAS**: ID, servidor,
porta, TLS e token do operador (use **MOSTRAR TOKEN** quando precisar).
Configure esses valores no aplicativo Flutter atual. O usuario do celular e
`operador` por padrao; confira o usuario autorizado no seu broker.
O nome visivel do equipamento nao altera os topics.

O instalador nao cria usuarios nem regras no broker. Antes de ligar o controle
do novo PC, cadastre/ajuste a credencial do PC e as permissoes do operador para
`pregacao/<novo-id>/`. Se o username do PC ficar vazio, o agente usa o ID como
username. Uma credencial antiga restrita a outro ID nao ganha acesso ao novo ID.

| Credencial | Publicar | Assinar |
|---|---|---|
| PC | `avail`, `state`, `events`, `history`, `ack`, `jobs` | `cmd` |
| Operador | `cmd` | `avail`, `state`, `events`, `history`, `ack`, `jobs` |

Cada nome acima e um topic completo sob `pregacao/<novo-id>/`; crie as regras
individuais conforme seu provedor e negue topics de outros equipamentos.
O operador pode receber acesso aos dois IDs quando precisar controlar ambos.
O estado retido ja leva os ultimos seis eventos ao celular, sem mudar as regras
do broker. Autorize `history` para uma lista maior de eventos retidos.
Nao use comandos retidos. Nunca use a mesma identidade nos dois PCs ativos.

**Substituir definitivamente o PC antigo:** desligue o controle no antigo e,
somente nesse caso, informe o ID antigo no cartao **CONTROLE REMOTO** do novo.
A escolha salva prevalece sobre o ID gerado; mantenha as permissoes e
credenciais correspondentes. Como a reinstalacao limpa gera um novo ID, repita
essa configuracao se quiser continuar usando a identidade antiga.

Depois de reiniciar, envie **STATUS** pelo celular e confirme ACK/estado atual.
O heartbeat local nao comprova a conexao MQTT. Nao use o script de teste EMQX
para essa conferencia: ele inicia e para uma gravacao real.

## Conferencia no destino

Faca uma gravacao curta e ouca o MP3, confira historico/pasta e repita sem
internet. Com conta e destinatario de teste conferidos, valide Drive,
NotebookLM/PDF, WhatsApp e STATUS/ACK do celular. Esses testes reais fazem parte
da sprint 3; o diagnostico local nao substitui o aceite no outro PC.
Registre os resultados usando [ACEITE_WINDOWS.md](ACEITE_WINDOWS.md), incluido no pacote.
