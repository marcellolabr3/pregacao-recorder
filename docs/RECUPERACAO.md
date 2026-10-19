# Recuperacao de gravacao

A captura grava segmentos WAV e metadados locais. Ao iniciar, o gravador procura
sessoes interrompidas e bloqueia nova gravacao ate resolver a recuperacao.

1. Verificar o aviso GRAVACAO INTERROMPIDA no painel.
2. Recuperar a sessao para consolidar o audio encontrado.
3. Ouvir o arquivo e conferir duracao antes de descartar qualquer material.
4. DESCARTAR e uma acao explicita que elimina os segmentos da sessao escolhida.

Nao desconectar energia/discos para testar em producao. Preparar gravacoes de teste
e backup para validar uma interrupcao real. Nenhuma queda foi provocada nesta retirada.
Jobs de estudos tambem persistem, mas a retomada do pipeline por etapa e pendente.
