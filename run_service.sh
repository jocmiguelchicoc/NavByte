#!/usr/bin/env bash
# ==============================================================================
# NavByte - Script de ejecución para el servicio systemd en segundo plano
# ==============================================================================
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
exec "$DIR/venv/bin/python" "$DIR/app.py" -p 5000
