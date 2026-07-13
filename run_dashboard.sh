#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
MODE="${1:-local}"
if [[ $# -gt 0 ]]; then shift; fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found at $PYTHON" >&2
  echo "Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

cd "$ROOT/modules/dashboard"
case "$MODE" in
  local) exec "$PYTHON" server.py --on-management-pc "$@" ;;
  tunnel) exec "$PYTHON" server.py --mode tunnel "$@" ;;
  stop) exec "$PYTHON" kill_dashboard.py "$@" ;;
  *) echo "Usage: $0 {local|tunnel|stop} [options]" >&2; exit 2 ;;
esac
