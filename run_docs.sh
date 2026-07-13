#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-dev}"

cd "$ROOT"
if [[ ! -d node_modules ]]; then
  echo "Documentation dependencies are missing. Run: npm ci" >&2
  exit 1
fi

case "$MODE" in
  dev|build|preview) exec npm run "docs:$MODE" ;;
  *) echo "Usage: $0 {dev|build|preview}" >&2; exit 2 ;;
esac
