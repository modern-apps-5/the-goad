#!/usr/bin/env bash
# Check the lab before the platform engineer automation demo: the
# platform engineer's Terraform plans no change, the two values are at
# their start, and the music store cluster has all its workers.
#
#   demos/platform-engineer-automation/check.sh <store context> <argo context>
#
# The contexts are the same as status.sh's. It starts the workflow
# platform-engineer as a plan only, so it takes a few minutes. It changes
# nothing.
#
# Needs gh, kubectl and jq. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

STORE_CONTEXT=${1:?usage: $0 <store context> <argo context>}
ARGO_CONTEXT=${2:?usage: $0 <store context> <argo context>}
STORE_NS=$(context_namespace "$STORE_CONTEXT")

ok=true

echo "Planning terraform/platform-engineer, without apply."
run_workflow platform-engineer.yml -f apply=false
plan_summary "$RUN_ID" || { ok=false; echo "The plan has changes. Find out whose they are before the demo."; }
echo

"$here/status.sh" "$STORE_CONTEXT" "$ARGO_CONTEXT" | tee "$DEMO_TMP/status"
grep -q 'memory_limit 48Gi; cluster workers replicas 2$' "$DEMO_TMP/status" ||
  { ok=false; echo "main is not at the start: run reset.sh."; }
grep -q 'music-store Synced, Healthy' "$DEMO_TMP/status" ||
  { ok=false; echo "Application music-store is not Synced and Healthy."; }
ready=$(kubectl --context "$STORE_CONTEXT" -n "$STORE_NS" get cluster music-store -o jsonpath='{.status.workers.readyReplicas}')
[[ $ready == 2 ]] || { ok=false; echo "The cluster has $ready ready workers, not 2."; }

echo
$ok && echo "Ready for the demo." || { echo "Not ready."; exit 1; }
