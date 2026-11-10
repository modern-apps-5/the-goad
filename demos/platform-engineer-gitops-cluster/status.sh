#!/usr/bin/env bash
# Where the demo stands: main, Argo CD's Application vks-addons, the
# cluster and its add-ons.
#
#   demos/platform-engineer-gitops-cluster/status.sh <argo context> [cluster context] [watch]
#
# <argo context> is your vcf context for platform-<suffix>. [cluster
# context] is the one for vks-addons-<suffix>, which exists once the
# workflow has made the namespace: see README.md. Without it, only main
# and Argo CD are shown. "watch" prints the state again every 15 seconds,
# until Ctrl-C.
#
# Needs gh, kubectl and jq. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> [cluster context] [watch]}
CLUSTER_CONTEXT=${2:-}
WATCH=${3:-}
if [[ $CLUSTER_CONTEXT == watch ]]; then
  CLUSTER_CONTEXT=
  WATCH=watch
fi

ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || { echo "Context $ARGO_CONTEXT has no namespace: see README.md" >&2; exit 2; }

show() {
  if on_main gitops/vks-addons/cluster.yaml; then
    echo "On main:      gitops/vks-addons/cluster.yaml is there"
  else
    echo "On main:      no cluster"
  fi

  local app
  app=$(kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application vks-addons --ignore-not-found -o json)
  if [[ -n $app ]]; then
    jq -r '"Argo CD:      vks-addons \(.status.sync.status), \(.status.health.status), at \(.status.sync.revision[0:7])"' <<<"$app"
  else
    echo "Argo CD:      no Application"
  fi

  [[ -n $CLUSTER_CONTEXT ]] || return 0
  local ns cluster
  ns=$(context_namespace "$CLUSTER_CONTEXT")
  cluster=$(kubectl --context "$CLUSTER_CONTEXT" -n "$ns" get cluster vks-addons --ignore-not-found -o json)
  if [[ -n $cluster ]]; then
    jq -r '"Cluster:      phase \(.status.phase), workers desired \(.status.workers.desiredReplicas), ready \(.status.workers.readyReplicas)"' <<<"$cluster"
  else
    echo "Cluster:      none"
  fi
  kubectl --context "$CLUSTER_CONTEXT" -n "$ns" get addoninstalls
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
