# Arquivo local `.OLD/`

Em 23/10/2026, os itens antigos foram separados dentro do próprio projeto.
`.OLD/` está no `.gitignore` porque contém backups e configurações privadas;
seu conteúdo não é enviado ao GitHub. A movimentação organiza o projeto, mas
não libera espaço em D:.
O arquivo local ocupa aproximadamente 5,25 GiB, sobretudo pelo backup de
recuperação (3,01 GiB) e pela montagem antiga (1,51 GiB).

| Em `.OLD/` | Conteúdo |
|---|---|
| `recovery/` | Backup de 20/10 e logs da migração do SSD, com dados pessoais antigos. |
| `build-stages/` | Montagem temporária do instalador anterior e saídas de testes. |
| `releases/` | `dist-pacote` genérico anterior; a entrega pessoal válida está na unidade E:. |
| `environments/` | `.venv.old`, substituída pela `.venv` ativa. |
| `source/` | Cliente Android Kotlin, ferramenta manual de migração e pastas vazias do Linux/Raspberry. |
| `packaging/` e `tests/` | Montadores e teste da antiga edição que levava gravações e sessões. |
| `docs/` | Guias, sprints, auditoria, contexto e registros de teste históricos. |
| `site/` | Site separado e antigo, inclusive seu repositório local. |

Permanecem na raiz os arquivos usados pelo programa em execução: `.venv/`,
`config/`, `data/`, `recordings/`, `logs/` e os diretórios ativos de código e
build. Os arquivos antigos de código permanecem recuperáveis no histórico Git.
Não executar os montadores arquivados sem revisar suas dependências e caminhos.
