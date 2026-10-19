# Google Drive

O gravador usa OAuth 2.0. O administrador fornece credenciais em
`config/google_credentials.json`, `.env` ou area tecnica do painel.
O usuario autoriza a conta pelo botao CONECTAR CONTA GOOGLE; nenhuma senha Google
fica no codigo. Tokens locais ficam fora do Git.

No navegador do proprio PC, abrir o painel pelo mesmo host usado no retorno OAuth
(por exemplo `http://localhost:8080` se `GOOGLE_REDIRECT_URI` usa localhost).
Retorno do painel: `/oauth/callback`. O conector do celular usa o protocolo
DRIVE_CONNECT/DRIVE_FINISH para completar a autorizacao no equipamento.

O upload confirma tamanho e MD5 quando fornecido pelo Drive. A fila persiste;
internet ausente ou erro agenda outra tentativa. Nao existe sessao de upload
persistida para reinicio do processo nem garantia completa contra duplicacao
quando o envio ocorre mas a confirmacao se perde.

Conectar/desconectar, testar pasta ou reenviar fila afeta a conta real.
Nao executar essas acoes como parte de uma revisao somente de leitura.
A saude do Drive nao substitui a autenticacao separada do NotebookLM.
