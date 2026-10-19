# Plano de desenvolvimento - instalacao pessoal em outro PC

Task: **PR-DIST-001 - Instalar meu Pregacao Recorder em outro PC**.
Escopo simplificado pelo usuario: manter todas as funcionalidades atuais,
com instalador simples e mesmas contas/servicos. Sprint 1 implementada em ZIP de teste.
Detalhes: [TASK_DISTRIBUICAO_WINDOWS.md](TASK_DISTRIBUICAO_WINDOWS.md).

| Sprint | Entrega | Estado |
|---|---|---|
| 1 | Pacote completo e runtimes privados | ZIP gerado; aceite em Windows limpo pendente |
| 2 | Instalador, atalho, configuracoes existentes e ajustes indispensaveis de login/inicio | Pendente |
| 3 | Validar funcoes atuais em Windows limpo e no PC destino; entregar guia curto | Pendente |

Substitui o plano anterior de oito sprints. Foram retirados recursos novos,
atualizador/rollback, CI, distribuicao publica e outras melhorias independentes.
Reutilizar o APK atual e as telas CONFIG; nao criar novo assistente ou migrador.
Problemas antigos seguem na [auditoria](../CONTEXTO_AUDITORIA_PRODUTO.md), sem
bloquear esta entrega quando nao impedirem a instalacao/uso atual nem causarem regressao.

350 testes e smoke local passaram. ZIP/instrucoes em [packaging](../packaging/README.md).
Proximo passo: instalador e configuracao pessoal (sprint 2); prova no destino (sprint 3).
Contexto: [CODEX_CONTEXT.md](CODEX_CONTEXT.md).
