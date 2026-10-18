# Integracao com Google Drive

Envio automatico das gravacoes finalizadas usando **OAuth 2.0**.
Nenhuma senha do Google e armazenada no Raspberry.

---

## 1. O que NAO fazer

* nao coloque email/senha do Google em nenhum arquivo do projeto;
* nao use "senha do app" salva em texto;
* nao commite `config/google_credentials.json` ou `config/google_token.json`
  (o `.gitignore` ja os exclui).

---

## 2. Criar as credenciais OAuth (uma unica vez, no PC)

1. Abra <https://console.cloud.google.com/>
2. Crie um projeto (ex.: `pregacao-recorder`);
3. **APIs e servicos -> Biblioteca** -> ative **Google Drive API**;
4. **APIs e servicos -> tela de consentimento OAuth**:
   * tipo de usuario: **Externo**;
   * preencha nome do app e e-mail;
   * em *Usuarios autorizados*, adicione o e-mail da conta da igreja
     (mesmo em modo teste);
5. **APIs e servicos -> Credenciais -> Criar credenciais -> ID do cliente OAuth**:
   * tipo de aplicativo: **Aplicativo de computador**;
   * nome: `pregacao-recorder`;
6. **Cadastre os dois valores na interface** (nao e preciso editar arquivo
   no equipamento): **CONFIG -> GOOGLE DRIVE** -> cole o *Client ID* e o
   *Client Secret* -> **SALVAR CONFIGURACOES**.

As credenciais ficam salvas apenas neste equipamento (em
`config/config.json`, fora do Git) e o **Client Secret nunca e devolvido**
pela interface - la ele aparece como "(secret definido)".

Ordem de preferencia (a interface tem prioridade):

```
Client ID/Secret digitados na interface   >   google_credentials.json   >   .env
```

Alternativas sem digitar na interface (opcionais):

```bash
scp client_secret_xxx.json pi@pregacao:/opt/pregacao-recorder/config/google_credentials.json
sudo chown pi:pi /opt/pregacao-recorder/config/google_credentials.json
sudo chmod 600 /opt/pregacao-recorder/config/google_credentials.json
```

ou preencher `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` em
`/opt/pregacao-recorder/.env`.

---

## 3. Conectar a conta pela interface

> **`GOOGLE_REDIRECT_URI` e obrigatorio** (em `.env`, com reinicio do
> servico). O Google so aceita redirect **loopback** para cliente do tipo
> aplicativo de computador.
>
> Testado em 2026-10-02 contra `accounts.google.com`, uma variante por vez:
>
> | `redirect_uri` | resposta do Google |
> |---|---|
> | `http://192.168.100.6:8080/oauth/callback` (IP privado) | `Error 400 invalid_request` — *device_id and device_name are required for private IP* |
> | IP privado **+** `device_id`/`device_name` | continua `invalid_request` (anexar os parametros **nao** resolve) |
> | `http://192.168.100.6.nip.io:8080/...` (hostname p/ IP privado) | `redirect_uri_mismatch` |
> | `http://192.168.100.6.localtest.me:8080/...` | `redirect_uri_mismatch` |
> | `http://localhost:8080/oauth/callback` | **aceito** (chega na tela de login) |
> | `http://127.0.0.1:8080/oauth/callback` | **aceito** (chega na tela de login) |
>
> Conectando a conta e uma operacao unica (o token vale depois); o tunel
> so e necessario nessa hora.

1. Confira em `/opt/pregacao-recorder/.env`:
   ```
   GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/callback
   ```
   e reinicie `sudo systemctl restart pregacao-recorder`;
2. abra o tunel SSH a partir do PC:
   ```
   ssh -L 8080:localhost:8080 <usuario>@<ip-do-pi>
   ```
3. no navegador abra **exatamente** `http://localhost:8080` — nao use o IP da
   rede local: o cookie de sessao fica no host, e o retorno do Google vem
   para `localhost` -> **CONFIG**;
4. seção **GOOGLE DRIVE** -> **CONECTAR CONTA**;
5. a propria aba navega para o login/autorizacao do Google (sem popup);
6. entre na conta da igreja e **permita** o acesso;
7. ao terminar, a mesma aba volta para a interface com o aviso
   *"Conta Google conectada ao Drive"*;
8. em CONFIG, **TESTAR PASTA** confirma que a pasta `Pregacoes` existe/foi criada.

O token e salvo em `config/google_token.json` (permissao `600`) e renovado
automaticamente quando expira.

> **Se a tela voltar para `localhost` e o navegador nao achar a pagina:**
> o tunel caiu. Reabra o `ssh -L` e recarregue. O importante e nao ter
> aberto a interface pelo IP, senao o cookie nao acompanha o retorno.

### Desconectar e TROCAR de conta

**CONFIG -> DESCONECTAR** apaga o token imediatamente. Depois:

1. **CONECTAR CONTA** - a tela do Google sempre abre com o **seletor de
   contas**, entao voce escolhe outra conta sem precisar deslogar do
   navegador;
2. autorize a nova conta;
3. **TESTAR PASTA** para confirmar que esta na conta certa.

Para trocar tambem as credenciais (outro projeto OAuth), edite *Client ID* /
*Client Secret* na mesma tela e **SALVAR CONFIGURACOES**. Para remover as
credenciais, apague o *Client ID* e salve (o secret e apagado junto).

---

## 4. Configuracoes de envio

| Campo | Efeito |
|---|---|
| **Client ID / Client Secret** | credenciais OAuth; salvas so neste equipamento |
| **Habilitar integracao** | liga/desliga todo o envio |
| **Upload automatico** | envia sozinho ao finalizar a gravacao |
| **Manter copia local** | desligado = apaga o local apos confirmacao |
| **Pasta de destino** | nome da pasta no Drive (criada se nao existir) |

---

## 5. Fluxo de envio e confirmacao

```
arquivo final consolidado
   │
   ├─ verificacao local (existe, tamanho > 0, cabecalho valido)
   ├─ registro na fila persistente (SQLite)
   ├─ upload resumivel (chunks de 8 MB)
   ├─ files().get(fileId)  -> compara SIZE com o local
   ├─ compara md5Checksum com o md5 local
   │
   └─ só entao: status DONE + notificacao "upload concluido"
```

**Um upload nao e considerado concluido porque a requisicao comecou.** A
confirmacao consulta o Drive e valida tamanho e MD5. Se qualquer coisa
divergir, o item volta para a fila.

---

## 6. Fila persistente

| Situacao | Comportamento |
|---|---|
| sem internet | arquivo fica no SSD, status `PENDING` |
| Drive fora do ar | nova tentativa com backoff (15s, 30s, 1m, 2m, 5m ... ate 30 min) |
| reinicializacao | a fila esta no SQLite e continua de onde parou |
| duplicidade | `file_path` e unico na tabela; o mesmo arquivo nunca vai duas vezes |
| Drive desconectado | aviso na interface; nada e perdido |

Estado na interface:

* **PENDING** = aguardando internet/Drive;
* **RUNNING** = enviando agora;
* **DONE** = confirmado.

Botão **REENVIAR FILA** zera o backoff de tudo que esta pendente.

---

## 7. Onde ficam os registros

Apos cada envio confirmado, a sessao recebe:

| Campo | Conteudo |
|---|---|
| `final_path` | caminho local do arquivo |
| `final_bytes` | tamanho |
| `duration_secs` | duracao |
| `drive_file_id` | id do arquivo no Drive |
| `drive_path` | `Pregacoes/2026-09-29_130000.mp3` |
| `ended_at` | data/hora |

Consultavel por `pregacao status` e pela tela de status.

Esses metadados sao o **preparo para a segunda etapa (NotebookLM)**: nome,
caminho, data, duracao e status ja estao registrados.

---

## 8. Problemas comuns

| Mensagem | Causa | Solucao |
|---|---|---|
| `credenciais OAuth ausentes` | nada cadastrado | cadastre Client ID/Secret na interface (secao 2) |
| `bibliotecas do Google nao instaladas` | pip incompleto | `.venv/bin/pip install -r requirements.txt` |
| `invalid_grant` | token revogado | DESCONECTAR e conectar de novo |
| `redirect_uri_mismatch` | URL de redirect divergente | defina `GOOGLE_REDIRECT_URI` |
| `invalid_request` (*device_id and device_name are required for private IP*) | `redirect_uri` aponta para IP da rede local | defina `GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/callback`, reinicie e abra a interface pelo tunel SSH (secao 3) |
| `verificacao de integridade falhou` | upload truncado | a fila tenta de novo automaticamente |
| `Google Drive nao conectado` | falta autorizar | CONFIG -> CONECTAR CONTA |
| `sem internet` | rede fora | nada a fazer; envia quando voltar |

Diagnostico:

```bash
pregacao status
pregacao logs -n 200
```
