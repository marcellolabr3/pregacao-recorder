# Pacote pessoal Windows - sprint 1

Monta um ZIP de teste com gravador, pipeline e runtimes privados. O `.exe` de
instalacao, configuracao pessoal e ajustes G01/G02 pertencem a sprint 2.

## Gerar

Na maquina de build: Windows x64, Python 3.11 com pip, Node/npm e FFmpeg/ffprobe
conhecidos. Essas ferramentas nao precisam estar instaladas no PC que usa o pacote.

```powershell
.venv\Scripts\python.exe -B packaging/build_bundle.py
```

O build baixa CPython embeddable 3.11.9 da origem oficial e verifica SHA256;
instala as 63 distribuicoes Python fixadas em `requirements-runtime.lock`, com
hashes, sem copiar `.venv`; usa `npm ci --omit=dev --ignore-scripts` com o lock
Node do componente. Chromium e incluido sem perfil autenticado. Pode aproveitar
somente binarios gerenciados do cache Playwright, conferidos pela revisao esperada:

```powershell
.venv\Scripts\python.exe -B packaging/build_bundle.py --browser-cache "$env:LOCALAPPDATA\ms-playwright"
```

`--node`, `--ffmpeg` e `--ffprobe` permitem indicar os executaveis de build;
`--output`, `--cache` e `--skip-zip` ajudam a repetir a montagem. Os binarios
copiados precisam ser autonomos; o smoke verifica Node, FFmpeg/DirectShow e
ffprobe com PATH isolado. Build requer internet/cache para dependencias, nao contas.

## Conteudo e uso

- `gravador/`: fontes, painel, defaults publicos e exemplos.
- `pipeline/`: fontes minimas e prompt preservado, template sem configuracao pessoal.
- `runtime/`: Python/bibliotecas, Node, FFmpeg/ffprobe e Chromium.
- `package-manifest.json`: origem da revisao, versoes e hashes dos arquivos.
- `Iniciar Pregacao.cmd` e `Verificar Pacote.cmd`: usam somente o Python do pacote.

Extraia a pasta completa para um destino gravavel. `Verificar Pacote.cmd` e
somente leitura; `Iniciar Pregacao.cmd` inicia o programa e cria os caminhos locais
iniciais se nao houver configuracao. Selecionar audio/pasta e conectar contas
continua necessario. Depois do primeiro uso, mover a pasta requer ajustar os
caminhos absolutos salvos em CONFIG; instalar no destino definitivo na sprint 2.

Saidas em `dist-pacote/`, cache em `.bundle-cache/`; ambos ignorados pelo Git.
O ZIP, logs de build e dependencias nao sao commitados. A copia de fontes usa
allowlist: nao leva `.env`, configuracao pessoal, banco, audios, logs, cookies,
QRs, perfis ou o `node_modules` do PC original. Node e instalado a partir do lock.

## Validar

O build executa `smoke_bundle.py` com o Python privado e ambiente isolado:
imports com origem conferida; PDF e XLSX locais; Chromium offline; versao do
NotebookLM; imports Node dentro do pacote; DirectShow e MP3 sintetico/ffprobe;
diagnostico do launcher sem gravar configuracao. Sem login, conexao de conta,
captura real, upload ou envio. Credenciais ausentes geram avisos esperados.

Para repetir o smoke, a partir da raiz deste repositorio:

```powershell
& 'CAMINHO-DO-PACOTE\runtime\python\python.exe' -B packaging/smoke_bundle.py 'CAMINHO-DO-PACOTE'
```

A prova neste PC com PATH isolado nao substitui Windows limpo, driver/interface
de audio e contas reais no destino. Essas provas permanecem na sprint 3.

Referencias: [task](../docs/TASK_DISTRIBUICAO_WINDOWS.md),
[Python embeddable](https://docs.python.org/3.11/using/windows.html#the-embeddable-package),
[Playwright browsers](https://playwright.dev/python/docs/browsers).

## Inventario de arquivos desta sprint

- `.gitignore`
- `app/bundled_runtime.py`
- `app/estudos.py`
- `app/launcher.py`
- `docs/CODEX_CONTEXT.md`
- `docs/SPRINTS.md`
- `docs/TASK_DISTRIBUICAO_WINDOWS.md`
- `docs/TESTES.md`
- `docs/WINDOWS.md`
- `iniciar-tudo.bat`
- `packaging/README.md`
- `packaging/build_bundle.py`
- `packaging/requirements-runtime.in`
- `packaging/requirements-runtime.lock`
- `packaging/smoke_bundle.py`
- `requirements.txt`
- `scripts/pregacao.cmd`
- `tests/test_bundle_builder.py`
- `tests/test_bundled_runtime.py`
- `tests/test_nlm_login.py`
- `tests/test_vendor_pipeline.py`
- `vendor/sermon-pipeline/.gitignore`
- `vendor/sermon-pipeline/README.md`
- `vendor/sermon-pipeline/SOURCE.json`
- `vendor/sermon-pipeline/config.example.json`
- `vendor/sermon-pipeline/package-lock.json`
- `vendor/sermon-pipeline/package.json`
- `vendor/sermon-pipeline/pipeline.py`
- `vendor/sermon-pipeline/prompt.txt`
- `vendor/sermon-pipeline/whatsapp/send.js`
