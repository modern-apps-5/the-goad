#!/usr/bin/env bash
# Start an incident walk: slow the store's catalog and open one Zammad
# ticket. It does not start the agents; the chat does that. "stop" puts
# the catalog back; it does not close the ticket.
#
#   STORE_URL=... ZAMMAD_URL=... ZAMMAD_TOKEN=... scripts/incident-walk.sh start
#   scripts/incident-walk.sh stop
#
# kubectl must point at the music store cluster.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  start) exec python3 "$here/incident-walk.py" ;;
  stop) exec python3 "$here/incident-walk.py" stop ;;
  *)
    echo "Usage: scripts/incident-walk.sh start|stop"
    echo "start slows catalog queries and opens the incident ticket."
    echo "stop makes catalog queries fast again."
    echo "It does not call the agents."
    exit 2
    ;;
esac
