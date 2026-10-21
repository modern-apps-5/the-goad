#!/usr/bin/env bash
# start slows the store and opens one Zammad ticket. It does not start the agents.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cmd="${1:-}"
case "$cmd" in
  start) exec python3 "$ROOT/demo/start.py" ;;
  *)
    echo "Usage: ./demo.sh start"
    echo "start slows catalog queries and opens the incident ticket."
    echo "It does not call the agents."
    exit 2
    ;;
esac
