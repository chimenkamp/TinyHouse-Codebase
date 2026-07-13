#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
PART="${1:-backend}"
if [[ $# -gt 0 ]]; then shift; fi

case "$PART" in
  backend)
    if [[ ! -x "$PYTHON" ]]; then
      echo "Python environment not found at $PYTHON" >&2
      echo "Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
      exit 1
    fi
    cd "$ROOT/Scotty - ROBOT ARM"
    exec "$PYTHON" -m uvicorn digital_twin.backend.app:app --reload --host 127.0.0.1 --port 8000 "$@"
    ;;
  frontend)
    cd "$ROOT/Scotty - ROBOT ARM/digital_twin/frontend"
    if [[ ! -d node_modules ]]; then
      echo "Frontend dependencies are missing. Run: npm ci --prefix 'Scotty - ROBOT ARM/digital_twin/frontend'" >&2
      exit 1
    fi
    exec npm run dev -- "$@"
    ;;
  *) echo "Usage: $0 {backend|frontend} [options]" >&2; exit 2 ;;
esac
