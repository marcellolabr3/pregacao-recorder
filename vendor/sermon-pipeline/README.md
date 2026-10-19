# Componente de estudos incorporado

Snapshot do pipeline usado pelo Pregacao Recorder. Origem dos cinco arquivos
copiados identificada por SHA-256 em `SOURCE.json`; o prompt foi preservado byte
a byte. Nao inclui configuracao real, credenciais, perfis, gravacoes, logs nem
os gravadores/bandejas alternativos da pasta original.

O contrato permanece `PYTHON pipeline.py AUDIO --skip-drive [--to NUMERO]`, com
os mesmos marcadores de progresso. Nao foram adicionados checkpoints/retries
persistentes ou mudancas no fluxo de autenticacao.

## Runtime e dados

- Python e NotebookLM: o interpretador corrente (`sys.executable`); comandos
  NotebookLM usam `python -m notebooklm`. A distribuicao Python e `notebooklm-py`.
- PDF: Markdown e xhtml2pdf no mesmo Python. Bibliotecas Python sao declaradas
  pelo manifesto do pacote do gravador, sem outra `.venv` aqui.
- Node: `PREGACAO_NODE` ou busca no PATH. `package-lock.json` fixa o conjunto
  Node/Baileys; validar a versao Node escolhida antes de distribuir.
- Dados: `PREGACAO_PIPELINE_HOME` ou esta pasta gravavel; entradas em `audio/`,
  resultados em `output/`, configuracao opcional em `config.json` e sessao/QRs
  WhatsApp em `whatsapp/auth/` e `whatsapp/qr_*.png` sob esse home.
- Defaults seguros: `config.example.json`, lido em memoria quando nao existe
  configuracao local; destinatario WhatsApp vazio. Nao cria configuracao real.
- Login e processamento herdam `NOTEBOOKLM_HOME`, `NOTEBOOKLM_PROFILE` e
  `PLAYWRIGHT_BROWSERS_PATH` definidos pelo launcher. Nao copiar perfil pessoal.
- Certificados opcionais sao herdados pelas variaveis padrao; nao procura o
  certificado particular ou PATH do registro da maquina de origem.
- `rclone` so e usado nos modos autonomos de upload/download Drive. O contrato
  integrado passa `--skip-drive` e o gravador usa sua propria integracao Google.

A copia da fonte externa original permanece intacta. Atualizar este snapshot
exige revisar o contrato e as adaptacoes acima. Nao incluir arquivos de sessao
ou configuracao real no instalador generico.
