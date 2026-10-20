# Plano de desenvolvimento - instalacao pessoal em outro PC

Novo ciclo de estabilidade, programacao, APK e inicio com Windows:
[tasks e sprints de 20/10/2026](TASKS_SPRINTS_20261020.md).
O restante deste arquivo registra o ciclo anterior de distribuicao Windows;
as entregas e pendencias atuais estao no plano acima e em
[CODEX_CONTEXT.md](CODEX_CONTEXT.md).

Task: **PR-DIST-001 - Instalar meu Pregacao Recorder em outro PC**.
Escopo atualizado pelo usuario: executar diretamente no SSD portatil com
configuracao, contas, historico e gravacoes atuais. Sprint 1 e implementacao
da sprint 2 concluidas. Edicao pessoal instalada no SSD e validada localmente;
o aceite de audio, contas e celular no outro PC segue na sprint 3.
Detalhes: [TASK_DISTRIBUICAO_WINDOWS.md](TASK_DISTRIBUICAO_WINDOWS.md).

| Sprint | Entrega | Estado |
|---|---|---|
| 1 | Pacote completo e runtimes privados | ZIP gerado; aceite em Windows limpo pendente |
| 2 | Instalador, atalho, configuracoes existentes e ajustes indispensaveis de login/inicio | Implementacao concluida; 488 testes verdes; aceite pessoal 2.2/2.3 no destino pendente |
| 3 | Validar funcoes atuais em Windows limpo e no PC destino; entregar guia curto | Edicao pessoal reinstalada em `E:\PregacaoRecorder-Pessoal`; integridade, diagnostico e captura curta de audio passaram. Abertura completa e aceite no outro PC pendentes. |

Em 20/10/2026 UTC, o instalador privado foi executado novamente no SSD apos a
pasta pessoal ter desaparecido da unidade. Ela foi restaurada e o instalador
foi copiado para a raiz do SSD. A pasta antiga `PregacaoRecorder` reapareceu
incompleta; o usuario depois autorizou eliminar pastas antigas quando o SSD
voltar a estar acessivel. Foram conferidos 7.859 arquivos publicos e
6.236 privados; banco integro com 12 gravacoes/12 uploads/2 estudos, links de
audio existentes, `.env`, token Google, perfil NotebookLM, 5.868 arquivos de
autenticacao WhatsApp e APK. O ID e o broker copiados coincidem com os defaults
do APK. O primeiro preparo realocou config e banco para `E:` e o diagnostico
do runtime privado passou. Guia: [GUIA_SSD_PORTATIL.md](GUIA_SSD_PORTATIL.md).

Artefato e evidencias atuais em [TESTES.md](TESTES.md). O instalador privado
e seu `.exe.sha256` estao no SSD e em `dist-pacote/`; nenhum entra no Git.
Configuracao em [GUIA_INSTALACAO_WINDOWS.md](GUIA_INSTALACAO_WINDOWS.md).
Audio selecionado pode ser testado antes de salvar; CONFIG valida/persiste o lote
e restaura memoria se falhar. MQTT pode ser salvo no cartao administrativo sem
editar `.env`, preservando segredos vazios e orientando reinicio completo.
Esses ajustes foram implementados; Windows limpo, contas/hardware e celular no
destino continuam necessarios para declarar o aceite completo.

Substitui o plano anterior de oito sprints. Foram retirados recursos novos,
atualizador/rollback, CI, distribuicao publica e outras melhorias independentes.
Reutilizar o APK atual e as telas CONFIG; nao criar novo assistente ou migrador.
Problemas antigos seguem na [auditoria](../CONTEXTO_AUDITORIA_PRODUTO.md), sem
bloquear esta entrega quando nao impedirem a instalacao/uso atual nem causarem regressao.

Validacoes atuais em [TESTES.md](TESTES.md). Artefatos/instrucoes em
[packaging](../packaging/README.md); configuracao no [guia curto](GUIA_INSTALACAO_WINDOWS.md).
Proximo passo: executar [ACEITE_WINDOWS.md](ACEITE_WINDOWS.md) em Windows limpo
e no PC destino, concluir configuracao/aceite de 2.2/2.3 e provas reais da sprint 3.
Contexto: [CODEX_CONTEXT.md](CODEX_CONTEXT.md).
