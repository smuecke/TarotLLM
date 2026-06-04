#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -d ".venv" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

exec "$PYTHON" -m uvicorn src.app:app --host 127.0.0.1 --port "${PORT:-8000}" --reload
