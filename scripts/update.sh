#!/usr/bin/env bash
# Compatibilidade: a atualizacao oficial agora e ./update.sh na raiz.
exec bash "$(cd "$(dirname "$0")/.." && pwd)/update.sh" "$@"
