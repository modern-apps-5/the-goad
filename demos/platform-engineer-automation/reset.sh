#!/usr/bin/env bash
# Put the lab back after the platform engineer automation demo: the music
# store namespace's memory limit back to 48Gi and the cluster back to two
# workers, the same way the demo changed them.
#
#   demos/platform-engineer-automation/reset.sh <store context>
#
# <store context> is your vcf context for the Supervisor Namespace
# music-store-<suffix>: see README.md.
#
# It opens one pull request with both values, merges it to main, and
# waits for Argo CD to take the third worker away. Then it runs the
# workflow platform-engineer with apply, which puts the memory limit back.
# What is already at its start is left alone, so it can run again after a
# failure.
#
# Needs gh, kubectl, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

STORE_CONTEXT=${1:?usage: $0 <store context>}
STORE_NS=$(context_namespace "$STORE_CONTEXT")
[[ -n $STORE_NS ]] || { echo "Context $STORE_CONTEXT has no namespace: see README.md" >&2; exit 2; }

MEMORY=48Gi
WORKERS=2

branch=demo-platform-engineer-reset-$(date +%Y%m%d%H%M%S)
new_branch "$branch"
changed=()
edit_file "$branch" terraform/platform-engineer/variables.tf \
  "s/(music-store = \\{.*?memory_limit\\s*=\\s*)\"[^\"]+\"/\${1}\"$MEMORY\"/s" \
  "Put the music store namespace's memory limit back to $MEMORY" &&
  changed+=(variables.tf) || [[ $? == 3 ]]
edit_file "$branch" gitops/music-store/cluster.yaml \
  "s/(name: workers\\n\\s+replicas: )\\d+/\${1}$WORKERS/" \
  "Put the music store cluster back to $WORKERS workers" &&
  changed+=(cluster.yaml) || [[ $? == 3 ]]

if ((${#changed[@]} == 0)); then
  delete_branch "$branch"
  echo "main is already at the start."
else
  merge_branch "$branch" "Platform engineer demo: put the lab back" \
    "After the platform engineer automation demo: memory_limit $MEMORY and $WORKERS workers for the music store. Opened by demos/platform-engineer-automation/reset.sh."
fi

# Argo CD polls git every few minutes, then CAPI deletes the worker.
workers_back() {
  (($(kubectl --context "$STORE_CONTEXT" -n "$STORE_NS" get machines -o name | wc -l) == WORKERS + 1)) &&
    [[ $(kubectl --context "$STORE_CONTEXT" -n "$STORE_NS" get cluster music-store -o jsonpath='{.status.workers.readyReplicas}') == "$WORKERS" ]]
}
wait_for "Cluster: back to $WORKERS workers" 1200 workers_back

echo "Applying terraform/platform-engineer."
run_workflow platform-engineer.yml -f apply=true
plan_summary "$RUN_ID" || true
echo "The lab is back at the start."
