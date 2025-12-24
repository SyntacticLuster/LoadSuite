#!/usr/bin/env bash
set -euo pipefail

# Keep output readable in Codespaces/Codex/Dev Containers logs.
echo "[devcontainer] Bootstrapping LoadSuite…"

# Useful for scripts/dev_server.sh (optional, but nice to have).
if command -v sudo >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends lsof
fi

python -m pip install -U pip
python -m pip install -U poetry

# Ensure Poetry creates the venv inside the repo (.venv)
poetry config virtualenvs.in-project true --local

# Install dependencies (including local editable path deps).
poetry install

echo "[devcontainer] Done. Try: poetry run pytest" 
