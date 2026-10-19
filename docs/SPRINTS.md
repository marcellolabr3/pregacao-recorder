# Plano de desenvolvimento - distribuicao Windows

Task atual: **PR-DIST-001 - Distribuicao instalavel do Pregacao Recorder**.
Estado: planejamento criado em 19/10/2026; nenhuma sprint de distribuicao iniciada.
Detalhamento, checklists, dependencias e criterios de aceite:
[TASK_DISTRIBUICAO_WINDOWS.md](TASK_DISTRIBUICAO_WINDOWS.md).

Objetivo: instalar gravador, agente, pipeline e runtimes em outro PC Windows
compativel, configurar contas pelo assistente e operar sem ambiente de desenvolvimento.

| Sprint | Entrega | Estado |
|---|---|---|
| 1 | Inventario, versoes do pipeline e build reproduzivel | Pendente |
| 2 | Correcoes da base: concorrencia, dados, validacoes e HTML | Pendente |
| 3 | Runtime independente, ferramentas e separacao codigo/dados | Pendente |
| 4 | Instalador e assistente de primeiro acesso | Pendente |
| 5 | Checkpoints, retomada, upload e WhatsApp sem repeticao cega | Pendente |
| 6 | Backup, transferencia entre PCs, atualizacao e rollback | Pendente |
| 7 | VM/PC limpos, audio real, dois celulares, APK e release | Pendente |
| 8 | Formularios Flutter, metadados e painel completo de jobs | Pendente |

Primeiro instalador candidato na sprint 4; liberacao depende da homologacao ate
a sprint 7. Sprint 5 pode avancar junto de 3/4 apos estabilizar base/contratos.
Sprint 8 e evolucao funcional e nao bloqueia a distribuicao quando seus limites
estiverem claros. Nao ha estimativa de prazo antes da prova da sprint 1.

A retirada Raspberry/Linux foi concluida: [REMOCAO_RASPBERRY.md](REMOCAO_RASPBERRY.md).
O iniciador Windows e login monitorado ja existem; preservar e corrigir limites
G01/G02 registrados na [auditoria](../CONTEXTO_AUDITORIA_PRODUTO.md).
Contexto de inicio de sessao: [CODEX_CONTEXT.md](CODEX_CONTEXT.md).

Proximo passo: sprint 1, inventario e prova de build limpo com componentes do
pipeline versionados; depois executar as correcoes bloqueantes da sprint 2.
