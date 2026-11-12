#!/usr/bin/env bash
# Test the cluster target: deploy a tiny workload into the VKS cluster
# through the Argo CD destination that managedentity-cluster.yaml
# registered. Not part of the demo; it only proves the registration works.
#
#   demos/platform-engineer-gitops-cluster/test-app.sh <argo context> [namespace context] [git ref]
#   demos/platform-engineer-gitops-cluster/test-app.sh --delete <argo context>
#
# It applies Application B (test/application.yaml), which syncs
# test/manifests into namespace demo of the cluster, and waits for it to be
# Healthy. --delete removes it again.
#
# Needs kubectl and jq. Prints no secret.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/common.sh"

if [[ ${1:-} == --delete ]]; then
  ARGO_CONTEXT=${2:?usage: $0 --delete <argo context>}
  ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
  [[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"
  echo "Removing the test Application $TEST_APP."
  kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" delete application "$TEST_APP" --ignore-not-found
  echo "Done."
  exit 0
fi

ARGO_CONTEXT=${1:?usage: $0 <argo context> [namespace context] [git ref]}
NS_CONTEXT=${2:-}
REVISION=${3:-$REVISION}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"

kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get managedentity "$CLUSTER_ENTITY" >/dev/null 2>&1 ||
  die "ManagedEntity $CLUSTER_ENTITY not found: run deploy.sh first."

echo "Application $TEST_APP: deploying the test workload into the cluster from $REVISION."
apply_tmpl test/application.yaml
wait_for "Argo CD: $TEST_APP Synced and Healthy" 600 app_ready "$TEST_APP"

echo "Done. The target works: Argo CD deployed into the cluster."
echo "Remove it with: $0 --delete \"$ARGO_CONTEXT\""
