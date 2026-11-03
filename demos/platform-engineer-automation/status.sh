#!/usr/bin/env bash
# Where the platform engineer automation demo stands: the two values on
# main, Argo CD's Application music-store, and the music store cluster's
# workers.
#
#   demos/platform-engineer-automation/status.sh <store context> <argo context> [watch]
#
#   demos/platform-engineer-automation/status.sh \
#     goad:music-store-8q8l6:default-project goad:platform-9pq9n:default-project watch
#
# <store context> is your vcf context for the Supervisor Namespace
# music-store-<suffix>, and <argo context> the one for platform-<suffix>,
# where Argo CD runs. README.md says how to make them. "watch" prints the
# state again every 15 seconds, until Ctrl-C.
#
# Needs gh, kubectl and jq. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

STORE_CONTEXT=${1:?usage: $0 <store context> <argo context> [watch]}
ARGO_CONTEXT=${2:?usage: $0 <store context> <argo context> [watch]}
WATCH=${3:-}

STORE_NS=$(context_namespace "$STORE_CONTEXT")
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $STORE_NS && -n $ARGO_NS ]] || { echo "Both contexts must point at a namespace: see README.md" >&2; exit 2; }

show() {
  local memory workers
  memory=$(main_file terraform/platform-engineer/variables.tf |
    perl -0ne 'print $1 if /music-store = \{.*?memory_limit\s*=\s*"([^"]+)"/s')
  workers=$(main_file gitops/music-store/cluster.yaml |
    perl -0ne 'print $1 if /name: workers\n\s+replicas: (\d+)/')
  echo "On main:      namespace music-store memory_limit $memory; cluster workers replicas $workers"

  kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application music-store -o json |
    jq -r '"Argo CD:      music-store \(.status.sync.status), \(.status.health.status), at \(.status.sync.revision[0:7])"'

  kubectl --context "$STORE_CONTEXT" -n "$STORE_NS" get cluster music-store -o json |
    jq -r '.status.workers | "Cluster:      workers desired \(.desiredReplicas), ready \(.readyReplicas)"'
  kubectl --context "$STORE_CONTEXT" -n "$STORE_NS" get machines -o json |
    jq -r '.items[] | "  \(.metadata.name)  \(.status.phase)"'
}

if [[ $WATCH == watch ]]; then
  while :; do
    date +%T
    show
    echo
    sleep 15
  done
else
  show
fi
