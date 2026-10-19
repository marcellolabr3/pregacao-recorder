# Plano de desenvolvimento - instalacao pessoal em outro PC

Task: **PR-DIST-001 - Instalar meu Pregacao Recorder em outro PC**.
Escopo simplificado pelo usuario: manter todas as funcionalidades atuais,
com instalador simples e mesmas contas/servicos. Implementacao ainda nao iniciada.
Detalhes: [TASK_DISTRIBUICAO_WINDOWS.md](TASK_DISTRIBUICAO_WINDOWS.md).

| Sprint | Entrega | Estado |
|---|---|---|
| 1 | Pacote completo: gravador, pipeline, ferramentas e dependencias; caminhos locais | Pendente |
| 2 | Instalador, atalho, configuracoes existentes e ajustes indispensaveis de login/inicio | Pendente |
| 3 | Validar funcoes atuais em Windows limpo e no PC destino; entregar guia curto | Pendente |

Substitui o plano anterior de oito sprints. Foram retirados recursos novos,
atualizador/rollback, CI, distribuicao publica e outras melhorias independentes.
Reutilizar o APK atual e as telas CONFIG; nao criar novo assistente ou migrador.
Problemas antigos seguem na [auditoria](../CONTEXTO_AUDITORIA_PRODUTO.md), sem
bloquear esta entrega quando nao impedirem a instalacao/uso atual nem causarem regressao.

Proximo passo: reunir e testar componentes/dependencias do pacote (sprint 1).
Contexto: [CODEX_CONTEXT.md](CODEX_CONTEXT.md).
