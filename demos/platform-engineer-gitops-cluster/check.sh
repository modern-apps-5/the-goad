#!/usr/bin/env bash
# Check the lab before the demo: the contexts resolve, every add-on has a
# release, and the demo is not already deployed. No Terraform, changes
# nothing.
#
#   demos/platform-engineer-gitops-cluster/check.sh <argo context> [namespace context]
#
# Needs kubectl. Prints no secret.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/common.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> [namespace context]}
NS_CONTEXT=${2:-}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"

ok=true

if grep -l RELEASE_FROM_LAB "$here"/gitops/*.yaml 2>/dev/null; then
  ok=false
  echo "These files have no release yet: see README.md."
fi

if kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application "$APP" >/dev/null 2>&1; then
  ok=false
  echo "Application $APP already exists: run reset.sh."
fi

for entity in "$NS_ENTITY" "$CLUSTER_ENTITY"; do
  if kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get managedentity "$entity" >/dev/null 2>&1; then
    ok=false
    echo "ManagedEntity $entity already exists: run reset.sh."
  fi
done

if [[ -n $NS_CONTEXT ]]; then
  ns=$(context_namespace "$NS_CONTEXT")
  if [[ -n $ns ]] && kubectl --context "$NS_CONTEXT" -n "$ns" get cluster "$CLUSTER" >/dev/null 2>&1; then
    ok=false
    echo "Cluster $CLUSTER already exists in $ns: run reset.sh."
  fi
fi

echo
$ok && echo "Ready for the demo." || { echo "Not ready."; exit 1; }
