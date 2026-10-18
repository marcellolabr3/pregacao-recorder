#!/usr/bin/env bash
# Compatibilidade: a desinstalacao oficial agora e ./uninstall.sh na raiz.
exec bash "$(cd "$(dirname "$0")/.." && pwd)/uninstall.sh" "$@"
