# Gerador de Estudo

Gravador de pregações para Windows, com painel local, envio ao Google Drive,
estudos no NotebookLM, entrega pelo WhatsApp e controle Android.

## Instalação pessoal

Os arquivos atuais estão em `dist-pacote-pessoal/` e na raiz de `E:\`:

- `Gerador de Estudo.exe` — instalador Windows x64;
- `Controle Android.apk` — aplicativo para o celular Android.

O instalador inclui as configurações MQTT, a autorização existente do Drive e
as sessões disponíveis do NotebookLM e WhatsApp. O APK `2.9.2` inclui a conexão
MQTT do operador. No celular, abra o menu **Conta NotebookLM** para usar
**DIAGNOSTICAR SESSAO** ou **RENOVAR LOGIN NO PC**. A validação e o login Google
acontecem no computador; o APK não pede a senha da conta. Os dois arquivos
contêm credenciais pessoais; mantenha-os fora do GitHub.

O APK `2.9.2` foi copiado para `E:\` em 24/10. O APK anterior `2.9.1` foi
preservado lá como `Controle Android 2.9.1.apk`.

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
