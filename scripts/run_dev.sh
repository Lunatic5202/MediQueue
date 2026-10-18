#!/usr/bin/env bash
# Initialize database, train the default proof-of-concept model (synthetic
# corpus — demonstration only), and start the API server with auto-reload.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=".venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY=python3
fi

export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -d artifacts/models ]] || [[ -z "$(ls -A artifacts/models 2>/dev/null || true)" ]]; then
  echo "==> No model artifacts found; training proof-of-concept model on synthetic corpus..."
  "$PY" scripts/train_model.py --task deterioration --dataset synthetic --n-patients 400
fi

echo "==> Starting MediQueue API on http://127.0.0.1:8000 (docs at /docs)"
exec "$PY" -m uvicorn mediqueue.app:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
