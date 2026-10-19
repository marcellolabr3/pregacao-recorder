# Arquitetura operacional

## Componentes

- Python/Flask/waitress: API e painel; estado oficial no PC Windows.
- SQLite: sessoes, uploads, eventos, jobs e programacao de pregacoes.
- FFmpeg/DirectShow: captura PCM continua; Python divide em segmentos WAV.
- Consolidacao: MP3/WAV validado antes de limpar segmentos.
- Drive OAuth: fila persistente, backoff, verificacao de tamanho/MD5.
- Estudos: fila persistente chama `pipeline.py` externo com `--skip-drive`.
- MQTT/TLS: processo separado consulta API e publica estado/eventos/progresso.
- Web/SSE e Flutter: exibem o estado e enviam comandos.

O gravador nao configura a rede do computador. Conectividade de internet mantida
em `app/network/connectivity.py`; interface de rede e administrada pelo Windows.
Armazenamento lista discos por API Windows e preserva o destino configurado.
Consultas nao criam pastas. Configurar destino pode criar a pasta explicitamente.

## Dados e atualizacao

Home padrao: pasta do projeto; override por `PREGACAO_HOME`.
Dados locais: `.env`, `config/config.json`, tokens, `data/`, `recordings/`, `recovery/`.
Manter esses itens ao atualizar. Nao sao parte de um pacote publico.

Jobs persistentes nao fornecem checkpoints completos ao pipeline externo;
retentativa pode repetir notebook/relatorio/PDF. Metadados existem no banco,
mas nao sao transmitidos ao estudo. A auditoria lista as demais pendencias.

Operacao e comandos: `docs/WINDOWS.md`. Testes: `docs/TESTES.md`.
Escopo de retirada e resultados: `docs/REMOCAO_RASPBERRY.md`.
