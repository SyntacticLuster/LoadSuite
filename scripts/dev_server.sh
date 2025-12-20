#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-8035}
APP_MODULE=${APP_MODULE:-app.main:app}
HOST=${HOST:-0.0.0.0}
RELOAD=${RELOAD:---reload}

# Clean up any lingering Uvicorn processes bound to the target port before starting.
if command -v lsof >/dev/null 2>&1; then
  existing=$(lsof -ti ":${PORT}")
  if [[ -n "${existing}" ]]; then
    echo "Stopping processes listening on port ${PORT}..."
    kill ${existing}
    # give the kernel a moment to release the socket
    sleep 0.5
  fi
fi

# Launch the dev server with Poetry-managed dependencies.
exec poetry run python -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" ${RELOAD}
