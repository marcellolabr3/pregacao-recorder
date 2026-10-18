# EMQX CLOUD - configuracao do broker do controle remoto

> Passo a passo para subir o broker MQTT/TLS que liga o equipamento
> (Raspberry) aos celulares dos operadores. Visao geral do controle remoto:
> `docs/AGENTE.md`. Modelo de ACL: `AGENTE.md`, secao 7.

O broker e o unico ponto de infraestrutura fora da igreja. Usamos o
**EMQX Cloud** (tem plano gratuito), que ja vem com TLS e painel de
usuarios/ACL - sem servidor proprio, sem porta aberta no roteador.

---

## 1. Criar o servidor (uma vez)

1. Conta em <https://cloud.emqx.com> (o plano **Free** serve: ate 100
   conexoes simultaneas - usamos 2: o aparelho e cada celular).
2. **Create Deployment** -> regiao proxima da igreja (ex.: `us-east-1`)
   -> plano **Free** -> protocolo **MQTT**.
3. No **Access Control** -> **Authentication**, criar autenticacao
   **Password Based** -> database interna (**Built-in database**).
4. Em **Access Control** -> **Authorization** -> **Built-in database**,
   criar as regras da secao 3 abaixo.
5. Anotar do painel (**Deployment** -> **Details**):
   * host: `xxx.xxx.emqxsl.com` (no exemplo atual: `d1901dc1.ala.us-east-1.emqxsl.com`)
   * porta TLS: `8883`
   Esses dois valores sao **publicos** (ficam no painel do equipamento e no
   app); ninguem conecta so por saber eles - a senha e obrigatoria.

---

## 2. Usuarios (uma vez)

Dois usuarios distintos - o aparelho **nao** reutiliza a senha do celular:

| Usuario | Senha | Quem usa |
|---|---|---|
| `pregacao-igreja-01` (= device_id; **ou outro nome**, ex.: `pregacao-pi`) | senha forte aleatoria (`PREGACAO_REMOTE_PASSWORD` no `.env` do Pi) | Raspberry, `pregacao-remote.service` |
| `operador` | **token compartilhado** (`PREGACAO_OPERATOR_TOKEN` no `.env`; digitado no app) | todos os celulares |

> Se o usuario do aparelho tiver outro nome (como `pregacao-pi`), registre
> em `PREGACAO_REMOTE_USERNAME` no `.env` do Pi: o padrao do codigo e o
> `device_id`, e o agente falha a autenticacao com o nome errado.

Criar em **Access Control** -> **Authentication** -> **Users** -> **Add
User** (mesma database da autenticacao).

---

## 3. ACL (uma vez)

Em **Authorization** -> **Rules**, as duas regras (substitua
`pregacao-igreja-01` pelo device_id real):

```
usuario "pregacao-igreja-01":
    allow publish   pregacao/pregacao-igreja-01/{avail,state,events,ack}
    allow subscribe pregacao/pregacao-igreja-01/cmd
    deny    everything else

usuario "operador":
    allow publish   pregacao/pregacao-igreja-01/cmd
    allow subscribe pregacao/pregacao-igreja-01/{avail,state,events,ack}
    deny    everything else
```

Resultado: o aparelho so publica estado/eventos/ack e so ouve comandos; os
celulares so publicam comandos e so ouvem o resto. Ninguem ve topicos de
outra igreja.

---

## 4. Trocar o token dos operadores (rotina)

O token e a **unica credencial que os celulares tem**. Se um celular for
perdido, ou periodicamente por precaucao:

1. Painel EMQX -> **Authentication** -> usuario `operador` -> editar a
   senha: gere um token novo (24+ caracteres aleatorios, ex.:
   `openssl rand -hex 16`).
2. Atualizar `.env` no Pi (`PREGACAO_OPERATOR_TOKEN=<token novo>`) e:
   ```bash
   sudo systemctl restart pregacao-remote
   ```
3. Em cada celular: app -> menu -> **Configuracoes** -> colar o novo
   token -> **SALVAR E CONECTAR**.

O aparelho (`pregacao-igreja-01`) **nao** e afetado: a senha dele e outra.
Celular perdido = trocar o token e atualizar so os que continuam legitimos.

---

## 5. Verificar sem subir gravacao

Com o agente instalado no Pi (ou qualquer cliente MQTT):

```bash
python scripts/emqx_check.py            # ciclo STATUS/START/START/STOP
python scripts/emqx_check.py STATUS     # so um comando
```

Falhas tipicas:

| Sintoma | Causa provavel |
|---|---|
| conexao recusada no Pi | senha do `aparelho` errada no `.env` |
| app diz "Broker recusou o usuario/token" | token errado/expirado no celular |
| `ack` nunca chega | ACL do `operador` sem publish em `cmd` |
| estado nunca atualiza | ACL do `operador` sem subscribe em `state` |

---

## 6. Custo e limites

* Plano **Free**: 100 conexoes, 100 GB/mes de trafego - folgado: o estado
  e < 1 KB, publicado a cada `PREGACAO_REMOTE_INTERVAL` (10 min) + eventos.
* Nao ha porta para abrir no roteador da igreja: a conexao **sai** do
  Raspberry (NAT amigavel) e os celulares tambem conectam de fora.
* Audio **nunca** trafega por aqui (so comandos e estado de texto).
