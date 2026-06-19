#!/usr/bin/env bash
set -euo pipefail

role="${1:-}"
shift || true

cd "$(dirname "$0")/.."

case "$role" in
  orchestrator)
    exec python3 -m tinyhouse.tinyhouse_orchestrator "$@"
    ;;
  arduino)
    exec python3 -m tinyhouse.tinyhouse_node --role arduino "$@"
    ;;
  camera)
    exec python3 -m tinyhouse.tinyhouse_node --role camera "$@"
    ;;
  *)
    echo "Usage: $0 {orchestrator|arduino|camera} [args...]" >&2
    exit 2
    ;;
esac

