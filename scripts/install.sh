#!/usr/bin/env bash
# Compatibilidade: a instalacao oficial agora e ./install.sh na raiz.
exec bash "$(cd "$(dirname "$0")/.." && pwd)/install.sh" "$@"
