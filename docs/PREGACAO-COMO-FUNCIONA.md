# PREGACAO RECORDER | COMO FUNCIONA NOSSO SISTEMA

Documento de apresentacao para pessoas que nao trabalham com programacao.
Atualizado em 18/10/2026 - descreve apenas o que ja esta funcionando.

---

## 1. O problema que queriamos resolver

Antes, depois de cada culto, alguem precisava:

* localizar o arquivo de audio gravado;
* renomear, organizar e enviar para um computador;
* transcrever e estudar a pregacao;
* montar um documento (estudo biblico) bonito;
* mandar esse documento para as pessoas pelo WhatsApp.

Era trabalhoso, demorado e dependia de alguem lembrar de cada passo. Com o
tempo, gravacoes se perdiam, estudos ficavam pela metade e a distribuicao
nunca saia no tempo certo.

---

## 2. Nossa solucao

O Pregacao Recorder e um sistema que acompanha a pregacao **do inicio ao
fim, sem precisar de ninguem lembrar dos passos**:

1. grava o culto no computador da igreja;
2. prepara o arquivo de audio (MP3);
3. envia para o Google Drive (nuvem da igreja);
4. manda o audio para o NotebookLM (ferramenta de inteligencia artificial do
   Google) com um roteiro de estudo ja definido;
5. recebe o estudo biblico pronto;
6. transforma em PDF;
7. envia pelo WhatsApp para o numero configurado.

O operador (a pessoa que cuida do PC) acompanha tudo pelo celular ou pelo
computador, de onde estiver.

---

## 3. Como funciona no dia a dia do operador

**Antes do culto**

* conferir, no celular, que o PC esta ligado e "PRONTO" (bola verde);
* opcional: preencher os dados da pregacao (pregador, tema, texto) - hoje a
  identificacao do estudo sai do proprio arquivo; o formulario esta em
  preparacao (ver item 12).

**Durante o culto**

* tocar em INICIAR GRAVACAO no celular (ou no painel do PC);
* o tempo de gravacao aparece correndo (cronometro);
* pode ficar no celular: qualquer celular conectado ve o mesmo estado.

**Depois do culto**

* tocar em FINALIZAR GRAVACAO (pede confirmacao para nao acabar por engano);
* a partir dai e automatico: MP3, Drive, NotebookLM, estudo, PDF, WhatsApp;
* quando chegar o PDF no WhatsApp, o estudo esta pronto.

**Se algo pedir atencao**

* o painel e o celular mostram a mensagem do que aconteceu, em portugues
  (exemplo: "AGUARDANDO ESTUDO: autenticacao expirada");
* nunca se perde o que ja foi concluido - o sistema guarda de onde parou.

---

## 4. Fluxograma completo da operacao

```
INICIAR GRAVACAO
      |
      v
CAPTURAR AUDIO  (mesa de som / microfone)
      |
      v
SALVAR E PREPARAR MP3  (valida arquivo, duracao e tamanho)
      |
      v
ENVIAR AO GOOGLE DRIVE  (upload confirmado por integridade)
      |
      v
PROCESSAR COM NOTEBOOKLM  (cria o notebook e transcreve o audio)
      |
      v
APLICAR O PROMPT DO ESTUDO  (roteiro fixo, aprovado pela igreja)
      |
      v
GERAR DOCUMENTO PDF  (com titulo padrao e nome padronizado)
      |
      v
ENVIAR PELO WHATSAPP  (numero configurado)
      |
      v
CONCLUIDO
```

**Quando alguma etapa falha:**

```
Falhou no NotebookLM (ex.: autenticacao expirada)
   -> o audio NO Drive fica salvo
   -> o sistema mostra "AGUARDANDO AUTENTICACAO" no celular
   -> avisa: "estudo pausado, nada se perdeu"
   -> assim que o login for renovado (um clique no painel),
      o processamento CONTINUA do ponto em que parou
      - sem regravar, sem reenviar ao Drive, sem PDF duplicado.
```

---

## 5. Como o celular se comunica com o computador

```
CELULAR (Wi-Fi ou 4G/5G)
      |
      v
EMQX CLOUD  (servico de mensagens na nuvem, sempre cifrado - TLS)
      |
      v
COMPUTADOR DA IGREJA  (conectado por cabo de rede)
```

* O celular **nao precisa estar na igreja**: funciona de casa, na rua, em
  qualquer operadora.
* O PC **nao precisa de Wi-Fi**: ele usa cabo (mais estavel).
* O PC e a unica "fonte da verdade": todos os celulares mostram a mesma
  informacao no mesmo instante.
* O celular apenas envia comandos e exibe estados - **nenhum processamento
  acontece no telefone**.
* Se a internet cair, o PC continua gravando normalmente (ver item 8).

---

## 6. Como funciona a barra de progresso

Hoje o acompanhamento ja mostra, em tempo real:

* estado geral (PRONTO / GRAVANDO / ENVIANDO / AGUARDANDO...);
* cronometro da gravacao;
* andamento do upload;
* fila e motivo de espera do estudo (quando houver).

A **barra de progresso por etapas** (verde = concluido, amarelo = aguardando,
vermelho = erro) esta em implementacao. Regra que ja esta definida e sera
seguida:

* durante a gravacao (duracao indefinida) mostra-se o **cronometro**, nunca
  um percentual inventado;
* depois de gravado, o percentual avanca **so por marcos reais concluidos**
  (MP3 ok, Drive ok, NotebookLM ok, PDF ok, WhatsApp ok);
* **100% so quando o WhatsApp confirmar o envio** - nunca antes.

Exemplo visual de como sera exibido (2 de 7 marcos reais concluidos):

```
  GRAVACAO ............. CONCLUIDO
  MP3 .................. CONCLUIDO
  GOOGLE DRIVE ......... ENVIANDO        <- em atividade (pisca)
  NOTEBOOKLM ........... PENDENTE
  ESTUDO BIBLICO ....... PENDENTE
  PDF .................. PENDENTE
  WHATSAPP ............. PENDENTE

  Progresso: 2 de 7 marcos (28%)   |   Proxima etapa: concluir o envio ao Drive
```

Se qualquer etapa falhar, a linha dela fica **VERMELHA com o motivo** - nada
de a barra chegar a 100% escondendo um problema.

---

## 7. Como os dados da pregacao entram no estudo

Hoje o estudo ja sai identificado com a data e o nome do arquivo da gravacao.

Em implementacao (Sprint 4 do plano tecnico):

```
PLANILHA (CSV/XLSX) OU FORMULARIO
            |
            v
CADASTRO DA PREGACAO  (data, horario, pregador, igreja, texto, tema)
            |
            v
ASSOCIACAO AUTOMATICA AO AUDIO  (pela data e hora do culto)
            |
            v
PROCESSAMENTO DO ESTUDO
            |
            v
DOCUMENTO COM PREGADOR, IGREJA, DATA, TEMA E TEXTO BASE
```

Os dados serao gravados **so no computador da igreja**; o celular apenas
exibe e edita os mesmos dados (nenhum celular guarda copia propria).

---

## 8. O que acontece quando a internet cai

| Funcao | Com internet | Sem internet |
|---|---|---|
| Gravar o culto | sim | **sim - continua gravando** |
| Salvar o MP3 local | sim | **sim** |
| Enviar ao Drive | sim | espera - envia sozinho ao voltar |
| NotebookLM / estudo / PDF / WhatsApp | sim | espera (precisa de nuvem) |
| Acompanhar pelo celular | sim | nao (o celular precisa de rede) |

Ao voltar a conexao, nada precisa ser refeito: a fila de envio retoma
automaticamente e as etapas ja concluidas nao se repetem.

---

## 9. Beneficios do sistema

* **Menos tarefas manuais**: o caminho inteiro roda sozinho apos o FINALIZAR.
* **Arquivos organizados**: MP3s com nome padronizado no Drive, com data.
* **Acompanhamento de qualquer lugar**: pelo celular, em tempo real.
* **Distribuicao simples**: o estudo chega pronto no WhatsApp.
* **Nada se perde**: queda de energia, queda de internet ou falha de
  autenticacao preservam tudo - o sistema avisa e retoma do ponto certo.
* **Reutilizacao**: os estudos ficam salvos em PDF para revisao.

(Observacao honesta: nao medimos "economia de horas" com numeros - por isso
nao apresentamos valores.)

---

## 10. Tecnologias utilizadas

| Tecnologia | O que e (em palavras simples) | Onde e usada |
|---|---|---|
| Python | linguagem de programacao do sistema | todo o PC (gravacao, painel, envios) |
| Flask + waitress | pequeno servidor que mostra o painel no navegador | painel web do PC |
| SQLite | banco de dados simples e local, dentro do PC | historico, fila de envios |
| FFmpeg | programa que junta e converte audio | gravaos -> MP3 |
| Google Drive | nuvem de arquivos da igreja | guardar as gravacoes |
| OAuth 2.0 | forma segura de "conectar a conta Google" sem copiar senha | acesso ao Drive |
| NotebookLM | ferramenta de IA do Google que transcreve e estuda o audio | geracao do estudo |
| MQTT + EMQX Cloud | canal de mensagens instantaneas, cifrado | celular <-> PC |
| TLS | "carta lacrada" da internet (ninguem le no caminho) | toda a comunicacao remota |
| Flutter | ferramenta que constroi o app do celular | APK Android (pronta p/ iOS) |
| Node.js + Baileys | programa que envia mensagem no WhatsApp | entrega do PDF |
| xhtml2pdf | converte o estudo em PDF | documento final |

---

## 11. Visao geral do sistema

```
                 +---------------------------+
                 |      CELULARES (APK)      |
                 |  iniciar/parar/acompanhar |
                 +-------------+-------------+
                               | Wi-Fi ou 4G/5G
                               v
                    +----------------------+
                    |   EMQX CLOUD (TLS)   |
                    +----------+-----------+
                               | saida segura
                               v
+----------------------------------------------------------+
|                PC DA IGREJA (cabo de rede)               |
|                                                          |
|  +------------------+   +-----------------------------+  |
|  | SISTEMA PRINCIPAL|   | AGENTE MQTT                 |  |
|  | gravacao + painel|<->| (fica ouvindo os comandos)  |  |
|  +--------+---------+   +-----------------------------+  |
|           |                                               |
|  +--------v---------+   +-----------------------------+  |
|  | BANCO (SQLite)   |   | PIPELINE DE ESTUDO          |  |
|  | historico/fila   |   | NotebookLM -> PDF -> Whats  |  |
|  +------------------+   +-----------------------------+  |
+----------------------------------------------------------+
           |                       |               |
           v                       v               v
     GOOGLE DRIVE           NOTEBOOKLM        WHATSAPP
   (gravacoes na nuvem)   (transcreve/estuda) (entrega o PDF)
```

---

## 12. O que ja esta pronto e o que ainda depende de melhorias

**Implementado e testado**

* gravacao pelo PC e pelo celular, com recuperacao apos queda de energia;
* consolidacao em MP3 com validacao;
* envio ao Google Drive com confirmacao e reenvio automatico;
* pipeline completo de estudo: NotebookLM -> prompt -> PDF -> WhatsApp
  (provado ao vivo em 18/10/2026, com PDFs recebidos no WhatsApp);
* autenticacao blindada: pausa "AGUARDANDO AUTENTICACAO" com aviso no
  celular, preservacao total e retomada automatica (provado ao vivo);
* painel web com estados, historico e saude das integracoes;
* controle remoto por MQTT/TLS com confirmacao (ACK) e reconexao sozinha;
* APK Android (versao 2.5) iniciando/parando e mostrando o estado;
* trava contra dois processos iguais no mesmo PC;
* 292 testes automatizados verdes.

**Em implementacao (proximas sprints - ver docs/SPRINTS.md)**

* barra de progresso por etapas no PC e no celular;
* gerenciador de trabalhos persistente (retomada apos reiniciar o PC);
* dados da pregacao (formulario, planilha CSV/XLSX, associacao e inclusao
  no documento);
* niveis de confirmacao do WhatsApp (preparado/solicitado/aceito/enviado);
* janelas de terminal eliminadas por completo;
* documentacao final (este manual em PDF, manual do operador, fluxogramas
  completos e relatorio de implementacao).

**Dependente de servico externo (limitacoes honestas)**

* a sessao do NotebookLM **pode expirar**; o sistema nao promete que nunca
  expira - ele detecta, preserva o audio, avisa e retoma apos o login
  (renovacao hoje e automatica na maioria dos casos);
* o WhatsApp confirma ate o nivel "aceito pelo servidor"; a entrega final
  na tela da pessoa nao e comprovavel pela ferramenta utilizada.

---

## 13. Conclusao

O Pregacao Recorder transforma uma corrente manual de tarefas num processo
organizado e silencioso: o PC trabalha, o celular acompanha, e o estudo
biblico chega pronto para quem precisa. Quando algo foge do normal, o
sistema avisa em portugues, guarda tudo o que ja foi feito e continua do
ponto certo quando o problema e resolvido.

Este documento sera atualizado a cada sprint concluida, para que sempre
descreva exatamente o que esta funcionando - nem mais, nem menos.
