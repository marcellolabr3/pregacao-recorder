# Recuperacao apos queda de energia

Este e o requisito mais critico do sistema: **nenhuma pregação pode sumir
porque a energia caiu.**

---

## Como o sistema se protege

```
INICIAR GRAVACAO
    │
    ├─ 1. sessao registrada no SQLite ANTES da primeira amostra
    ├─ 2. session.json gravado em recordings/.sessions/<id>/
    ├─ 3. arecord escreve PCM continuamente
    ├─ 4. o processo fecha o cabecalho WAV de cada segmento a cada N segundos
    └─ 5. segmento_0001.wav  segmento_0002.wav  segmento_0003.wav ...

QUEDA DE ENERGIA no meio do segmento_0003:
    segmento_0001.wav  ✅ integro
    segmento_0002.wav  ✅ integro
    segmento_0003.wav  ⚠ com o cabecalho desatualizado (ultimo write incompleto)
```

Ao religar, o servico:

1. abre o banco e procura sessoes ainda marcadas como `RECORDING`;
2. **repara o cabecalho WAV** de cada segmento (`app/audio/wav.py: repair`);
3. calcula duracao e tamanho recuperaveis;
4. marca a sessao como `RECOVERY_REQUIRED`;
5. exibe o aviso na interface web;
6. **nao apaga nada**.

Diretorios orfaos (banco corrompido, microSD trocado) tambem sao detectados:
o `session.json` permite reconstruir a sessao.

---

## O que o usuario ve

```
⚠ GRAVACAO INTERROMPIDA

Uma gravacao foi interrompida inesperadamente (queda de energia ou
reinicializacao). O audio encontrado esta preservado e NAO sera apagado
automaticamente.

  Inicio: 29/09/2026 09:30:00   Duracao recuperada: 00:41:12
  Tamanho: 35.4 MB              Segmentos: 42

  [ RECUPERAR ]   [ DESCARTAR ]
```

### RECUPERAR

1. repara os cabecalhos;
2. consolida os segmentos em um unico arquivo (`.../2026/09/2026-09-29_093000.mp3`);
3. verifica a integridade do arquivo final;
4. **so entao** apaga os segmentos;
5. entra na fila de upload;
6. estado final: `COMPLETED` (ou `UPLOADING`).

Se a conversao falhar, os segmentos **permanecem** e o item volta para a lista
de recuperacao com o motivo do erro - basta tentar de novo.

### DESCARTAR

Pede confirmacao e remove os segmentos. Nunca roda automaticamente.

---

## Teste de recuperacao (obrigatorio na validacao)

```bash
sudo ./scripts/power_loss_test.sh
```

O script:

1. autentica na API local;
2. inicia uma gravacao;
3. espera 25 s;
4. **mata o servico com SIGKILL** (simula corte de energia);
5. reinicia o servico;
6. confirma que `/api/recovery` devolve a gravacao interrompida;
7. chama o endpoint de recuperacao;
8. mostra `pregacao status` com o resultado.

### Teste manual completo (recomendado)

1. abra a interface pelo celular;
2. **INICIAR GRAVACAO** e aguarde ~1 minuto;
3. **puxe o cabo de energia** do Raspberry (nao use `shutdown`);
4. reconecte a energia e aguarde o boot;
5. abra a interface: o painel **GRAVACAO INTERROMPIDA** deve aparecer com a
   duracao ja recuperada;
6. toque em **RECUPERAR**;
7. confira o arquivo em `/mnt/ssd/pregacoes/2026/09/...`;
8. abra o arquivo no NotebookLM ou no player para validar o audio;
9. confira o envio em **UPLOAD PENDENTE/CONCLUIDO**.

---

## Reinicio planejado (systemd stop/restart)

Ao receber `SIGTERM` o servico:

1. encerra a captura com `SIGINT` no `arecord` (fecha o ultimo segmento);
2. grava o cabecalho correto dos segmentos;
3. atualiza a sessao no banco;
4. **mantem os segmentos** - na proxima subida a interface oferece recuperacao.

Nenhum audio e descartado em reinicio planejado.

---

## Diagnostico remoto (sem monitor)

```bash
pregacao status      # lista gravacoes interrompidas e duração recuperada
pregacao recovery    # detalhes: id, inicio, duracao, segmentos, diretorio
pregacao logs -n 200
journalctl -u pregacao-recorder --since "1 hour ago"
```

Eventos registrados:

| Evento | Significado |
|---|---|
| `boot` / `servico iniciado` | subida normal do servico |
| `gravacao_iniciada` | captura comecou |
| `segment_started` | novo segmento aberto |
| `capture_gap` | interface USB caiu e foi reconectada |
| `gravacao_finalizada` | stop recebido |
| `conversao` | consolidacao em andamento |
| `gravacao_pronta` | arquivo final verificado |
| `recuperacao` | queda de energia detectada |
| `erro` | falha com detalhe no log |

---

## Por que nao existe "apagamento automatico"

Uma gravacao interrompida so e removida quando o usuario escolhe
**DESCARTAR**. O sistema prefere ocupar espaco a perder uma pregação.

A retencao automatica (`storage.retention_days`) **nao** alcança sessoes
pendentes de recuperacao - ela so limpa arquivos ja consolidados.
