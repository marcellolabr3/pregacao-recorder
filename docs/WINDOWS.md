# Windows - instalacao e operacao

Este guia descreve a instalacao manual atual. O instalador completo para outros
PCs ainda sera desenvolvido: task [PR-DIST-001](TASK_DISTRIBUICAO_WINDOWS.md),
com sprints e criterios de aceite em [SPRINTS.md](SPRINTS.md).

## Requisitos

Windows 10/11, usuario logado, Python 3.11+, FFmpeg no PATH e interface de audio.
O FFmpeg faz captura DirectShow e consolidacao; e necessario mesmo para gravar WAV.

## Preparar

Na raiz do projeto, no PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Nao sobrescrever um `.env` existente. Preencher apenas durante a instalacao inicial:
PINs opcionais, segredo de sessao, credenciais OAuth e MQTT conforme os guias.
Nenhuma migracao de banco ou de pasta e exigida pela retirada da plataforma antiga.
O home padrao e a pasta do projeto; `PREGACAO_HOME` continua suportado.

## Iniciar

Abrir `iniciar-tudo.bat`. Ele usa o Python da `.venv`, verifica dependencias,
FFmpeg e disponibilidade da porta, inicia gravador e agente MQTT como processos
separados e ocultos e abre o navegador quando a API estiver pronta. Painel padrao:
`http://127.0.0.1:8080`; PIN, porta configurada e `PREGACAO_HOME` continuam validos.
Cliques repetidos reutilizam os processos existentes. Falha do agente nao encerra
o gravador. Em caso de erro, a janela mostra a orientacao e aguarda uma tecla.

As opcoes usam o mesmo arquivo; executar no PowerShell, na pasta do projeto:

```powershell
.\iniciar-tudo.bat --verificar
.\iniciar-tudo.bat --sem-navegador
.\iniciar-tudo.bat --somente-gravador
.\iniciar-tudo.bat --somente-agente
```

`--somente-agente` nao abre o navegador; o agente aguarda a API se ela estiver fora do ar.
Os BATs separados de gravador/agente e os diagnosticos antigos de SSD foram
substituidos por essas opcoes. Atalhos existentes para `iniciar-tudo.bat` continuam validos.

Para iniciar com o Windows, criar atalho para `iniciar-tudo.bat --sem-navegador`
na pasta `shell:startup`. O usuario precisa entrar na sessao. Antes de reiniciar
processos, conferir que nao ha captura, conversao, upload ou estudo executando.

## Audio e armazenamento

Selecionar interface em CONFIG > CONFIGURACOES AVANCADAS > AUDIO. A deteccao usa
FFmpeg/DirectShow e prefere USB. O padrao e PCM 16 bits durante a captura.
A pasta padrao fica em `recordings/`. A lista de destinos inclui o destino atual,
a pasta padrao e discos locais fixos/removiveis. Para pasta personalizada, usar
o assistente inicial ou API `/api/storage` com PIN administrativo.
Disco indisponivel impede nova gravacao; nao existe troca automatica para outro volume.

## Diagnostico

`iniciar-tudo.bat --verificar` consulta requisitos sem iniciar os servicos: imports
essenciais do gravador, FFmpeg/ffprobe e disponibilidade de Node/rclone, presenca dos
credenciais do Drive (painel, arquivo ou ambiente), token e caminhos configurados do pipeline externo. Nao
exibe segredos nem confirma logins, entrega pelo WhatsApp ou todas as dependencias
do pipeline. Requisitos opcionais ausentes devem ser avaliados conforme as
integracoes usadas.

Para acompanhar uma instancia em execucao:

```powershell
scripts\pregacao.cmd status
scripts\pregacao.cmd doctor
scripts\pregacao.cmd logs -n 80
scripts\pregacao.cmd logs -f
```

`doctor` consulta pastas, FFmpeg, interface, credenciais e API local. `check` captura
2 segundos para medir sinal; executar somente quando quiser testar audio.
`start`/`stop` da CLI controlam uma gravacao real.

Os logs de inicializacao ficam em `logs/inicializacao.log`, `logs/inicio-gravador.log`
e `logs/inicio-agente.log`. Os servicos continuam usando `logs/pregacao.log` e
`logs/pregacao-agente.log`. O script `_instalador/ajustar_caminhos.py` e uma ferramenta
manual de migracao antiga: altera caminhos e nao e executado pelo iniciador.

## Atualizar

Fechar gravador/agente somente quando ociosos; guardar backup; atualizar fontes e
reinstalar dependencias se necessario. Preservar `.env`, `config/config.json`, tokens,
`data/`, `recordings/` e `recovery/`. Reabrir `iniciar-tudo.bat` e atualizar o navegador.
O pipeline externo possui instalacao/dependencias separadas.

## Arquivos da melhoria de inicializacao (19/10/2026)

Criados: `app/launcher.py`, `tests/test_launcher.py`.

Alterados: `iniciar-tudo.bat`, `app/api/routes.py` (orientacao exibida),
`app/remote/agent.py` (documentacao), `README.md`, `GUIA-USUARIO.md`,
`docs/WINDOWS.md`, `docs/AGENTE.md`, `docs/TESTES.md`, `docs/CODEX_CONTEXT.md`.

Removidos:

- `iniciar-gravador.bat`
- `iniciar-agente.bat`
- `_instalador/subir-painel-teste.bat`
- `_instalador/testar-agente-ssd.bat`
- `_instalador/verificar-deps-pregacao.bat`
- `_instalador/verificar-deps-sermon.bat`
- `_instalador/verificar-identidade.bat`
- `_instalador/verificar-playwright.bat`
- `_instalador/verificar-runtimes.bat`
- `_instalador/verificar-tudo.bat`
