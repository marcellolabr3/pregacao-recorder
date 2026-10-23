# Gerador de Estudo

Gravador de pregações para Windows, com painel local, envio ao Google Drive,
estudos no NotebookLM, entrega pelo WhatsApp e controle Android.

## Instalação pessoal

Os arquivos prontos estão na raiz de `E:\` e em `dist-pacote-pessoal/`:

- `Gerador de Estudo.exe` — instalador Windows x64;
- `Controle Android.apk` — aplicativo para o celular Android.

O instalador inclui as configurações MQTT, a autorização existente do Drive e
as sessões disponíveis do NotebookLM e WhatsApp. O APK inclui a conexão MQTT do
operador e os botões **DIAGNOSTICAR SESSAO** e **RENOVAR LOGIN NO PC** para o
NotebookLM. Os dois arquivos contêm credenciais pessoais; mantenha-os fora do
GitHub.

Instale o `.exe` no computador e o `.apk` no celular. No primeiro uso, escolha a
interface de áudio e a pasta de gravação no painel e faça uma gravação curta.
Se o NotebookLM indicar sessão expirada, use **RENOVAR LOGIN NO PC** e conclua a
entrada na conta Google no navegador do computador. A instalação começa sem
gravações ou histórico antigos.

Siga o [guia de instalação](docs/GUIA_INSTALACAO_CONECTADA.md) e confira o
[estado dos testes desta entrega](docs/TESTES.md).

## Desenvolver e gerar novos pacotes

O código do painel está em `app/` e `web/`; o app Android está em
`flutter/pregacao_controle/`. Para gerar novamente o instalador e o APK pessoais
com as conexões atuais:

```powershell
.venv\Scripts\python.exe -B packaging/build_connected_release.py --output "dist-pacote-pessoal\Gerador de Estudo.exe"
```

Para gerar a edição pública sem credenciais, execute
`.venv\Scripts\python.exe -B packaging/build_release.py`. Consulte
[packaging/README.md](packaging/README.md) para requisitos e opções de build.
