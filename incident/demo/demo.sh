#!/usr/bin/env bash
# Approved 2026-10-14. Do not run until the pull request is merged and the cluster exists.
# start does not call storage_load. Live disk load stays off. VCF replay stays on.
# Presenter commands for the Metal Music Store incident.
# start slows the store and opens the ticket. It does not call the agents.
set -euo pipefail
# This file lives in incident/demo. The package root is incident/.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SSL_CERT_FILE="${SSL_CERT_FILE:-${HOME}/.config/tanzu-ca/ca-bundle.pem}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
PY="$ROOT/.venv/bin/python"

usage() {
  cat <<'EOF'
Usage: ./demo.sh <command>

  start     Slow the store's database path and open the incident ticket.
            Does not call the agents and does not copy the ticket.
  enrich    Backup. Enrich the latest open incident ticket from this machine.
  deny      Show the AgentMinder denial.
  pii       File the scrubbed personal-data ticket.
  restore   Remove the database delay and wait until the store answers HTTP 200.
  reset     Close open helpdesk tickets. Tickets whose title says backup stay open.
            Clears the Incident live board so it starts empty.

The incident title is: Metal Music Store slow: checkout and catalog pages taking 10+ seconds

Enrichment in the room: open the incident response agent chat and type
  pick up the latest incident ticket and enrich it
EOF
}

cmd="${1:-}"
case "$cmd" in
  start) exec "$PY" orchestrator/demo_start.py ;;
  # 60 minutes is the backstop. Expected time on 4 vCPU is 20 to 40 minutes.
  enrich) exec timeout 3600 "$PY" orchestrator/enrich.py --latest ;;
  deny) exec "$PY" orchestrator/incident_k8s_deny.py ;;
  pii) exec "$PY" orchestrator/pii_ticket.py ;;
  restore) exec "$PY" fault-injection/fault.py --restore ;;
  reset) exec "$PY" orchestrator/reset_tickets.py ;;
  *) usage; exit 2 ;;
esac
