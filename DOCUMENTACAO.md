# DOCUMENTACAO - pregacao-recorder

Este arquivo explica **o que o sistema faz**, passo a passo, em linguagem
simples. e o documento principal para quem quer entender o equipamento.

> Complementos:
> * `INSTALACAO-RASPBERRY.md` - instalacao tecnica, do zero
> * `GUIA-USUARIO.md` - somente o que o usuario final precisa saber
> * `CHECKLIST.md` - lista de validacao antes de colocar em uso
> * `docs/REDE.md` - Ethernet, Wi-Fi, Access Point e acesso remoto
> * `docs/AGENTE.md` - controle remoto (APK Android) e o agente
> * `docs/` - referencias tecnicas (audio, Drive, recuperacao, testes)

---

## 1. Visao geral

O pregacao-recorder e um **aparelho de gravacao dedicado**. Ele fica ligado
permanentemente na igreja, conectado a mesa de som, e grava pregacoes,
reunioes e eventos. Depois de gravar, ele envia o arquivo para o Google Drive
automaticamente - mesmo que a internet caia no meio do caminho.

O usuario interage apenas pelo celular, pelo navegador. Nao ha aplicativo para
instalar, nao ha conta para criar, nao ha tela de login de sistema operacional.

```
                         SISTEMA COMPLETO

  Mesa Soundcraft
        |
        |  (saida MIX L/R da mesa)
        v
  Interface de audio USB           <-- converte som analogo em digital
        |
        |  (USB)
        v
  Raspberry Pi 3 Model B+          <-- roda a aplicacao e a interface web
        |
        |  (USB)
        v
  SSD / HD externo                 <-- grava os arquivos em disco
        |
        |  (internet da igreja)
        v
  Google Drive (pasta Pregacoes)   <-- copia em nuvem
        |
        v
  NotebookLM / qualquer player     <-- voce abre e estuda o audio
```

### Funcao de cada componente

| Componente | O que faz | Por que existe |
|---|---|---|
| Mesa Soundcraft | Recebe os microfones e entrega o som "mesclado" | e de la que sai o audio da pregacao |
| Interface de audio USB | Converte o som analogo da mesa em digital para o computador | o Raspberry nao tem entrada de audio de qualidade |
| Raspberry Pi 3 B+ | Executa o programa: grava, salva, controla, envia | computador pequeno, barato e silencioso, feito para ficar ligado 24h |
| SSD/HD USB | Guarda os arquivos de audio | disco rapido e com espaco para meses de gravacoes |
| Google Drive | Nuvem onde o arquivo final e copiado | qualquer pessoa com acesso pode ouvir; alimenta o NotebookLM |
| NotebookLM (ou similar) | Estuda/transcreve o arquivo baixado | **fora do Raspberry** - o equipamento nao faz IA nenhuma |
| Celular | Abre a interface web para controlar | nao ha botao fisico: o navegador e o controle |

### O que o sistema NAO faz

* Nao grava video.
* Nao faz transcricao nem inteligencia artificial no Raspberry.
* Nao controla o NotebookLM - ele apenas deixa o arquivo pronto na nuvem.
* Nao envia e-mail nem mensagem: tudo acontece na interface web.
* Nao funciona fora da rede local da igreja (por seguranca).

---

## 2. Fluxo completo de uma gravacao

### 2.1 Ao clicar em [ INICIAR GRAVACAO ]

1. **O Raspberry verifica se ja existe uma gravacao em andamento.**
   Se existir, ele recusa o clique (nunca ha duas gravacoes ao mesmo tempo).
2. **Verifica se ha armazenamento disponivel** no SSD (espaco minimo
   configuravel). Sem espaco, ele recusa e avisa.
3. **Verifica se a interface de audio esta disponivel.** Sem interface USB
   reconhecida, ele recusa: o sistema nunca finge que gravou.
4. **Inicia a captura** com `arecord` na interface selecionada.
5. **Cria os arquivos temporarios** em `recordings/.sessions/`, em segmentos
   de 60 segundos (padrao). Segmentos curtos limitam a perda se a energia
   faltar - e o usuario nunca ve os segmentos, ve um arquivo so.
6. **Atualiza o estado para `RECORDING`** (gravando).
7. **A interface web passa a mostrar GRAVANDO** - a atualizacao chega por
   SSE (evento no servidor), nao e preciso recarregar a pagina.
8. **O cronometro comeca** na tela, contando a duracao real da gravacao.
9. **O audio e salvo no armazenamento local**, segmento a segmento, com o
   tamanho crescente visivel na tela ("Arquivo" e "Segmentos").

> O navegador nunca decide se o Raspberry esta gravando: ele apenas exibe o
> estado que o servidor manda. Se o celular desligar, a gravacao continua.

### 2.2 Ao clicar em [ FINALIZAR GRAVACAO ]

1. **Confirmacao**: abre a pergunta
   *"Tem certeza que deseja finalizar a gravacao?"* - com a duracao atual.
   Sem confirmacao, nada e finalizado (evita clique acidental).
2. **Encerramento da captura**: o `arecord` e finalizado com SIGTERM e os
   segmentos restantes sao fechados.
3. **Finalizacao do arquivo**: cabecalhos WAV corrompidos (se houver) sao
   reparados; a sessao e marcada como `FINALIZING`.
4. **Conversao**: com `ffmpeg`, os segmentos viram **um arquivo MP3 unico**
   (sem ffmpeg, o arquivo fica em WAV).
5. **Validacao do arquivo**: tamanho minimo e integridade sao conferidos.
   Se falhar, o estado vira `ERROR` e os segmentos ficam preservados.
6. **Armazenamento definitivo**: o arquivo final e movido para a estrutura
   por data, ex.: `recordings/2026/09/2026-09-29_193000.mp3`.
7. **Entrada na fila de upload**: a sessao e registrada no SQLite com
   status `PENDING` - a fila e persistente, sobrevive a reinicio.
8. **Upload para Google Drive** (se a conta estiver conectada e a internet
   disponivel): o worker de upload envia o arquivo para a pasta configurada.
9. **Confirmacao**: o servidor confere o tamanho do arquivo no Drive
   (integridade) e grava o `drive_file_id` - **nunca ha upload duplicado**,
   pois a sessao ja enviada sai da fila.
10. **Atualizacao do status**: a interface mostra `PRONTO` de novo, o
    historico mostra a gravacao com "ENVIADO", e uma notificacao aparece
    na tela.

Se a internet estiver fora no passo 8, nada se perde: veja a secao 4.

> **Caso especial - gravacao vazia**: se a finalizacao acontece antes de
> qualquer byte chegar do microfone (FINALIZAR imediatamente apos INICIAR),
> nao ha o que converter. Nesse caso o sistema **nao entra em erro**: ele
> descarta a sessao vazia, avisa *"Gravacao vazia descartada - nenhum audio
> foi capturado"* e volta para `IDLE`.

---

## 3. Queda de energia durante a gravacao

```
queda de energia
      |
      v
Raspberry desliga (gravacao e interrompida no meio)
      |
      v
energia retorna
      |
      v
Raspberry inicia automaticamente (boot)
      |
      v
systemd inicia a aplicacao (Restart=always, After=network-online)
      |
      v
aplicacao verifica o estado anterior (tabela sessions no SQLite)
      |
      v
detecta gravacao interrompida (sessao aberta + segmentos em .sessions/)
      |
      v
preserva/recupera os arquivos (cabecalho WAV de cada segmento e reparado)
      |
      v
notifica atraves da interface web (banner ATENCAO + cartao GRAVACAO INTERROMPIDA)
```

O que aparece na tela quando o equipamento volta:

* Banner **ATENCAO** no topo.
* Cartao **GRAVACAO INTERROMPIDA** com inicio, duracao recuperada, tamanho
  e quantidade de segmentos.
* Dois botoes: **RECUPERAR** (consolida o que existia e finaliza o arquivo)
  e **DESCARTAR** (apaga - pede confirmacao dupla).
* Nada e apagado automaticamente, nunca.

### Limitacoes fisicas (importante, sem ilusao)

* Enquanto o Raspberry **esta desligado**, ele **nao pode enviar
  notificacao nenhuma**. Nao ha milagre: sem energia, nao ha rede.
* A notificacao acontece **quando o equipamento voltar a funcionar**.
* O audio gravado **ate o instante da queda** e preservado nos segmentos.
* O audio dos ultimos instantes pode ser perdido: o segmento em andamento
  (ate 60 s) pode ficar incompleto - por isso a recuperacao repara o
  cabecalho e, se necessario, descarta apenas o ultimo segmento.
* Se a queda ocorrer durante a **conversao/finalizacao**, o sistema
  recupera os segmentos brutos e permite finalizar de novo na tela.

---

## 4. Internet indisponivel

```
gravacao
   |
   v
finalizacao
   |
   v
internet indisponivel
   |
   v
arquivo permanece no SSD (local)
   |
   v
UPLOAD PENDENTE (fila persistente no SQLite)
   |
   v
internet retorna (verificada a cada poucos segundos)
   |
   v
upload automatico (worker retoma a fila)
   |
   v
UPLOAD CONCLUIDO (tamanho conferido no Drive)
```

Regras:

* **Gravar nao depende de internet.** A gravacao e 100% local.
* A fila de upload vive no banco de dados: se o Raspberry reiniciar
  (ou a luz cair), a fila continua de onde parou.
* Enquanto pendente, a tela mostra "pendentes: N" e o status OFFLINE.
* O botao **REENVIAR FILA** (tela principal) força a retomada imediata.
* **O sistema nao perde uma gravacao so porque a internet caiu.**

---

## 5. Google Drive

### 5.1 Visao tecnica (administrador)

* **Autenticacao:** OAuth 2.0 oficial do Google, escopo `drive.file`
  (+ `openid`/`email` para exibir o e-mail da conta conectada).
  O sistema **nao pede nem guarda senha do Google** - apenas o token de
  autorizacao. Nao existe tela de login falsa: a janela e do Google.
* **Credenciais da aplicacao:** cadastradas **uma unica vez** pelo
  administrador, no deploy, em uma destas formas (nesse nivel de prioridade):
  1. interface: `CONFIGURACOES AVANCADAS -> GOOGLE DRIVE (TECNICO)`;
  2. arquivo `config/google_credentials.json` (recomendado no install);
  3. variaveis `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` no `.env`.
  O usuario final **nunca** ve Client ID ou Client Secret.
* **Conectar a conta:** botao `CONECTAR CONTA GOOGLE` ->
  `/api/drive/connect` -> janela oficial do Google (na mesma aba, com
  `prompt=consent select_account`, permitindo trocar de conta) ->
  `/oauth/callback` -> token salvo.
* **Onde fica o token:** `config/google_token.json`
  (`GOOGLE_TOKEN_FILE`), gravado com permicao restrita. e o unico artefato
  que liga o equipamento a conta da igreja.
* **Upload:** worker proprio (`app/upload/queue.py`) com fila persistente,
  tentativas com backoff e conferencia de integridade (tamanho) apos o envio.
  Sessoes ja enviadas ficam com `drive_file_id` - upload duplicado nao ocorre.
* **Pasta de destino:** nome configuravel (`drive.folder_name`, padrao
  `Pregacoes`); a pasta e criada/reutilizada no Drive e o `folder_id` fica
  guardado em `config/config.json`.
* **Verificar se enviou:** tela `HISTORICO` mostra "ENVIADO" +
  caminho no Drive; a tela principal mostra "concluidos: N".
* **Desconectar:** `CONFIG -> DESCONECTAR` apaga o `google_token.json`
  (a pasta e os arquivos continuam no Drive).
* **Reconectar:** mesmo botao `CONECTAR CONTA GOOGLE`; pode-se escolher
  **outra conta** na janela do Google (o fluxo pede a escolha de conta).
* **Token expirado/revogado:** o sistema renova sozinho com o refresh
  token quando expira; se o Google recusar (revogado pelo usuario ou
  mudanca de senha), o status vira `DESCONECTADO`, as gravacoes continuam
  na fila e a tela pede para reconectar - nada e apagado.

### 5.2 Explicacao simples (usuario final)

1. Voce clica em **CONECTAR CONTA GOOGLE**.
2. Abre a janela do Google (a mesma de sempre): digite o e-mail e a senha
   **na propria tela do Google**.
3. O Google permissao para guardar arquivos na sua pasta - clique em permitir.
4. A tela volta para o equipamento mostrando **● CONECTADO**, o e-mail da
   conta e a pasta.
5. A partir dai, toda gravacao finalizada e enviada sozinha.
6. Para trocar de conta: **DESCONECTAR** e depois **CONECTAR** de novo.
7. Nenhuma senha sua fica guardada no Raspberry - so a autorizacao.

---

## 6. Interface web

A interface abre no navegador do celular (mesma rede Wi-Fi). Aparelho
dedicado: `LIGAR -> ABRIR PELO CELULAR -> INICIAR -> GRAVANDO -> FINALIZAR
-> CONFIRMAR -> UPLOAD -> CONCLUIDO`.

### 6.1 Tela principal (GRAVAR)

| Estado na tela | Significado |
|---|---|
| **PRONTO** | nada em andamento; pode iniciar |
| **GRAVANDO** | captura em andamento; cronometro rodando |
| **FINALIZANDO** | consolidando segmentos/convertendo (aguarde) |
| **ENVIANDO** | arquivo sendo enviado ao Drive |
| **CONCLUIDO** | gravacao pronta e salva |
| **ATENCAO** | gravacao interrompida detectada - ver cartao de recuperacao |
| **ERRO** | falha; o cartao explica o motivo e os arquivos estao preservados |

Tambem exibem: armazenamento (espaco livre), rede (ONLINE/OFFLINE),
interface de audio (com TESTAR SINAL), Google Drive (status/envios),
ultima gravacao e notificacoes.

### 6.2 Tela de gravacao

* **INICIAR GRAVACAO** - comeca; botao desabilitado enquanto grava.
* **Cronometro** - duracao ao vivo, inicio, tamanho e segmentos.
* **FINALIZAR GRAVACAO** - habilitado **so durante** a gravacao e sempre
  pede confirmacao: *"Tem certeza que deseja finalizar a gravacao?"*
  com **CANCELAR** e **FINALIZAR**.
* Nao existe botao unico que alterne entre gravar/parar.

### 6.3 Tela de HISTORICO

Cada linha mostra:

* **Data** da gravacao;
* **Duracao**;
* **Tamanho**;
* **Status** (CONCLUIDA / INTERROMPIDA / ERRO...);
* **Upload** (ENVIADO / PENDENTE);
* **Google Drive** (caminho do arquivo na nuvem).

No topo: total de arquivos e espaco ocupado em disco.

### 6.4 Tela de CONFIGURACOES (usuario comum)

* **EQUIPAMENTO** - nome exibido no topo.
* **GOOGLE DRIVE** - status (`● CONECTADO` / `○ NAO CONECTADO`), conta,
  pasta e os botoes **CONECTAR CONTA GOOGLE**, **TESTAR CONEXAO**,
  **DESCONECTAR**. Nao ha campos tecnicos aqui.
* **CONFIGURACOES AVANCADAS** - abre a area do administrador.

### 6.5 CONFIGURACOES AVANCADAS (administrador)

Protegida por PIN de administrador (`PREGACAO_ADMIN_PIN`; se nao definido,
usa o PIN normal). Contem:

* **AUDIO** - dispositivo, formato, sample rate, canais, encoder, bitrate,
  tamanho do segmento, indicacao do ffmpeg;
* **ARMAZENAMENTO** - pasta local, espaco minimo, retencao;
* **GOOGLE DRIVE (TECNICO)** - habilitar/auto upload/manter copia, pasta,
  Client ID/Secret (so aqui, so para o admin), teste de pasta;
* **REDE E LOGS** - servidor/porta de teste de internet, intervalo de
  nova tentativa e visor de `logs/pregacao.log`;
* Ao sair sem PIN de admin, o servidor recusa a gravacao (HTTP 403) - a
  protecao existe **no servidor**, nao so na tela.

### 6.6 Assistente de PRIMEIRO ACESSO

Abre automaticamente na primeira vez que alguem entra com o PIN, e some
depois (marca `setup.completed`). Passos:

1. **Audio** - escolher interface + TESTAR AUDIO;
2. **Armazenamento** - pasta + espaco disponivel;
3. **Google Drive** - CONECTAR GOOGLE DRIVE (opcional);
4. **Finalizacao** - resumo + **CONCLUIR CONFIGURACAO**.

Tambem pede o PIN do administrador quando for trocar algo tecnico.

### 6.7 Acesso e seguranca da interface

* PIN de acesso (`PREGACAO_PIN`) para tudo que altera estado;
* PIN de administrador (`PREGACAO_ADMIN_PIN`) para configuracoes avancadas;
* A interface so responde na rede local da igreja (nao exponha o servidor
  a internet).

---

## 7. Rede e acesso remoto

A camada de rede existe para uma unica meta: **o equipamento nunca fica
inacessivel**.

### 7.1 Ethernet e Wi-Fi

* A Ethernet e reconhecida sozinha - nenhuma configuracao manual.
* O Wi-Fi e configuravel pela tela (CONFIG -> REDE): procurar redes,
  conectar, desconectar, esquecer. As operacoes pedem PIN de administrador.
* Enquanto existir Ethernet ou Wi-Fi util, nenhum outro caminho e ativado.

### 7.2 Access Point de configuracao (rede de emergencia)

Se o equipamento ficar **sem nenhuma rede util**, ele passa a emitir a
propria rede `PREGACAO-PI-XXXX` (senha `pregacao12345`, endereco
`192.168.50.1`). Voce conecta o celular nela e continua usando o painel em
`http://192.168.50.1:8080`.

* Tolerancia: **45 s** se existe rede salva tentando reconectar,
  **12 s** se nao ha nada configurado.
* Com a rede de volta, o Access Point e **desligado sozinho**.
* Ha um botao explicito (**ATIVAR MODO DE CONFIGURACAO**) para ligar essa rede
  quando quiser, com aviso de confirmacao.
* Um watchdog (`pregacao-netwatch`) observa tudo a cada 15 s, antes do servico
  de gravacao subir, e registra as transicoes no journal com as tags
  `[NETWORK]` e `[TAILSCALE]`.

A gravacao **nunca e interrompida** por mudanca de rede: a camada de rede e
independente da captura de audio e da fila de upload.

### 7.3 Acesso remoto (Tailscale)

Para ver o equipamento de fora da igreja usa-se **Tailscale**, que cria um
tunel privado criptografado entre os aparelhos da conta:

* **sem** port forwarding, **sem** UPnP, **sem** abrir porta no roteador;
* o painel passa a responder tambem em `http://<ip tailscale>:8080`;
* a autenticacao e feita pelo botao **AUTENTICAR** (PIN de administrador) e o
  link oficial do Tailscale - nenhuma credencial fica guardada no equipamento.

Detalhes tecnicos, API, logs e solucao de problemas: `docs/REDE.md`.

### 7.4 Seguranca

* Operacoes de rede exigem PIN de administrador (o servidor responde `403`,
  nao e so escondimento de botao).
* A senha do Wi-Fi nunca aparece em tela, log, processo ou resposta de API.
* A senha do Access Point so existe no `.env` (`chmod 600`) e o Access Point
  **sempre** tem senha.
* A regra do polkit autoriza somente o usuario do servico e somente o
  prefixo `org.freedesktop.NetworkManager.`; o sudoers do Tailscale e uma
  lista fechada de subcomandos.
* Nao ha firewall adicionado: nao existe porta aberta no roteador da igreja,
  o painel so e alcancavel na rede local e, para fora, apenas pelo tunel do
  Tailscale. A avaliacao esta registrada em `docs/REDE.md`.

---

## 8. Controle remoto (APK Android)

### 8.1 O que e

E possivel **iniciar, encerrar e acompanhar** uma gravacao pelo celular,
de qualquer lugar, sem estar na igreja e sem mexer no roteador.

Funciona assim: o equipamento abre uma conexao de saida para um servico
remoto (a mesma tecnologia de mensagens usada por aplicativos de chat) e o
APK conversa por ali. Como a iniciativa vem **do equipamento**, nao ha port
forwarding, IP publico, DDNS nem abertura de porta - nada e preciso
configurar no roteador da igreja.

```
celular (APK) <--Internet--> servico remoto <--saida--> Raspberry Pi
```

### 8.2 O que aparece no celular

* **ONLINE / OFFLINE** - se o equipamento esta alcancavel;
* **PRONTO / GRAVANDO** - estado atual;
* **TEMPO** - duracao da gravacao em curso;
* **[ INICIAR ]** e **[ ENCERRAR ]** - os mesmos botoes do painel;
* **Upload: ENVIANDO -> ENVIADO** - progresso do envio ao Drive;
* o **nome do arquivo** quando a gravacao termina.

O APK **nao grava audio** e **nao recebe audio**: ele apenas controla e
observa. O som continua sendo captado e salvo no SSD do equipamento.

### 8.3 E se a Internet cair?

* A **gravacao nao para**: o audio e salvo localmente, sempre.
* O APK mostra o equipamento como **OFFLINE** enquanto nao houver Internet.
* Os arquivos ficam na fila e sobem ao Drive quando a conexao voltar
  (estado `UPLOAD_PENDING`), sem duplicar e sem apagar o local antes da
  confirmacao.
* Se o equipamento reiniciar, ele volta sozinho e o agente reconecta.

### 8.4 Quem pode usar

* O operador digita, uma unica vez em **Configuracoes**, o host do broker,
  o ID do aparelho e o **token do operador**; depois fica guardado no
  celular. O usuario ja vem preenchido como `operador` (e a senha dele e
  o `PREGACAO_OPERATOR_TOKEN` - nunca a senha do aparelho).
* Host, ID e token sao exibidos no painel, no cartao **CONTROLE REMOTO**,
  apenas para quem tem o PIN de administrador.
* O usuario final nao ve o token nem nenhuma credencial.
* Os comandos continuam protegidos pelo PIN local do equipamento: o agente
  autentica na API como qualquer operador do painel.

### 8.5 Importante

* O controle remoto **nao substitui** o painel local: ele continua sendo
  o metodo principal quando alguem esta la.
* Se o agente parar por qualquer motivo, **nada se perde**: gravacao,
  recuperacao de quedas e upload seguem funcionando. O controle remoto e
  um acrescimo, nunca um requisito.
* O painel mostra o status do agente no cartao **CONTROLE REMOTO**
  (ID do aparelho, host, estado do servico).

Detalhes tecnicos (topics, estados, eventos, comandos, logs e solucao de
problemas): `docs/AGENTE.md`.
