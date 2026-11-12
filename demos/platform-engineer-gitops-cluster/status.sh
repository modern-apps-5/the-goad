#!/usr/bin/env bash
# Where the demo stands: the Argo CD Applications, the two ManagedEntity
# targets, the cluster and its add-ons.
#
#   demos/platform-engineer-gitops-cluster/status.sh <argo context> [namespace context] [watch]
#
# <argo context>      vcf context for platform-<suffix>, where Argo CD runs.
# [namespace context] vcf context for the namespace the cluster is in. Adds
#                     the cluster phase and the AddonInstalls. Omit for the
#                     Applications and targets only.
# [watch]             print the state again every 15 seconds, until Ctrl-C.
#
# Needs kubectl and jq. Prints no secret.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/common.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> [namespace context] [watch]}
NS_CONTEXT=${2:-}
WATCH=${3:-}
if [[ $NS_CONTEXT == watch ]]; then NS_CONTEXT=; WATCH=watch; fi

ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"

app_line() {
  local app json
  json=$(kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application "$1" --ignore-not-found -o json)
  if [[ -n $json ]]; then
    jq -r --arg a "$1" '"Application:  \($a) \(.status.sync.status), \(.status.health.status), at \(.status.sync.revision[0:7])"' <<<"$json"
  else
    echo "Application:  $1 none"
  fi
}

entity_line() {
  if kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get managedentity "$1" >/dev/null 2>&1; then
    echo "ManagedEntity: $1 present"
  else
    echo "ManagedEntity: $1 none"
  fi
}

show() {
  app_line "$APP"
  app_line "$TEST_APP"
  entity_line "$NS_ENTITY"
  entity_line "$CLUSTER_ENTITY"

  [[ -n $NS_CONTEXT ]] || return 0
  local ns cluster
  ns=$(context_namespace "$NS_CONTEXT")
  cluster=$(kubectl --context "$NS_CONTEXT" -n "$ns" get cluster "$CLUSTER" --ignore-not-found -o json)
  if [[ -n $cluster ]]; then
    jq -r '"Cluster:      phase \(.status.phase), workers desired \(.status.workers.desiredReplicas // 0), ready \(.status.workers.readyReplicas // 0)"' <<<"$cluster"
  else
    echo "Cluster:      none"
  fi
  kubectl --context "$NS_CONTEXT" -n "$ns" get addoninstalls 2>/dev/null || true
}

if [[ $WATCH == watch ]]; then
  while :; do date +%T; show; echo; sleep 15; done
else
  show
fi
