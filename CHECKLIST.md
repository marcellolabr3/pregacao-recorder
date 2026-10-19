# Checklist de validacao Windows

Marcar somente depois de observar no equipamento real.

- [ ] Iniciar-tudo abre gravador e agente sem instancias duplicadas.
- [ ] Painel abre sem erros JavaScript e sem controles de rede do equipamento.
- [ ] PINs existentes funcionam conforme a configuracao.
- [ ] Interface de audio correta aparece; teste de sinal responde.
- [ ] Celular inicia e finaliza gravacao; START repetido nao duplica captura.
- [ ] MP3 final pode ser ouvido; historico confere duracao/tamanho.
- [ ] Destino configurado permanece; sem disco nova captura e recusada.
- [ ] Consulta de destinos nao cria pastas em outros discos.
- [ ] Sem internet o audio e preservado; upload aguarda e retoma.
- [ ] Drive recebe o arquivo com integridade conferida.
- [ ] Sessao interrompida e recuperavel em teste preparado.
- [ ] NotebookLM sinaliza autenticacao quando exigida.
- [ ] Pipeline gera PDF e WhatsApp com limite de confirmacao declarado.
- [ ] Dois celulares observam o mesmo estado e reconectam.
- [ ] Reinicio controlado preserva jobs e banco.
- [ ] Atualizacao preserva credenciais, banco e gravacoes.

A suite automatizada foi executada em ambiente isolado, nao substitui este
checklist de hardware. Resultados e limites em `docs/TESTES.md`.
