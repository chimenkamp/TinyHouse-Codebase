#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
ROLE="${1:-}"
if [[ $# -gt 0 ]]; then shift; fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found at $PYTHON" >&2
  echo "Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt" >&2
  exit 1
fi

cd "$ROOT/extensions/sage"
case "$ROLE" in
  broker) exec "$PYTHON" broker/broker_main.py "$@" ;;
  sensor) exec "$PYTHON" sensor_node/sensor_main.py "$@" ;;
  orchestrator) exec "$PYTHON" -m tinyhouse.tinyhouse_orchestrator "$@" ;;
  arduino) exec "$PYTHON" -m tinyhouse.tinyhouse_node --role arduino "$@" ;;
  camera) exec "$PYTHON" -m tinyhouse.tinyhouse_node --role camera "$@" ;;
  *) echo "Usage: $0 {broker|sensor|orchestrator|arduino|camera} [options]" >&2; exit 2 ;;
esac
