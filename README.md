# Gerador de Estudo

Gravador de pregações para Windows, com painel local, envio ao Google Drive,
estudos no NotebookLM, entrega pelo WhatsApp e controle Android.

## Instalação pessoal

Os arquivos atuais estão em `dist-pacote-pessoal/` e na raiz de `E:\`:

- `Gerador de Estudo.exe` — instalador Windows x64;
- `Controle Android.apk` — aplicativo para o celular Android.

O instalador inclui as configurações MQTT, a autorização existente do Drive e
as sessões disponíveis do NotebookLM e WhatsApp. O APK `2.9.3` já inclui a
conexão MQTT do operador e usa somente o PC vinculado nesta entrega. No celular,
abra **Configurações** para usar **DIAGNOSTICAR SESSAO** ou
**RENOVAR LOGIN NO PC**; a tela principal não mostra esses comandos. A validação
e o login Google acontecem no computador. Os campos de servidor, porta, TLS,
ID e token não são editáveis nesta edição pessoal; em Configurações você pode
alterar a aparência sem interromper a conexão. Os dois arquivos contêm
credenciais pessoais; mantenha-os fora do GitHub.

O APK `2.9.3` foi copiado para `E:\` em 24/10. A versão anterior `2.9.2`
ficou preservada lá com seu número no nome.

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
