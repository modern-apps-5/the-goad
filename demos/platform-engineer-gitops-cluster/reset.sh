#!/usr/bin/env bash
# Put the lab back: remove the test workload, the cluster and its add-ons,
# and the two Argo CD targets. The namespace is reused, so it is left as it
# was. No Terraform.
#
#   demos/platform-engineer-gitops-cluster/reset.sh <argo context> <namespace context>
#
# It deletes, in order:
#   1. Application B, if present (prunes the test workload);
#   2. Application A (its finalizer prunes the cluster and the add-ons),
#      then waits for the cluster to be gone;
#   3. the two ManagedEntity targets.
# What is already gone is skipped, so it can run again after a failure.
#
# Needs kubectl and jq. Prints no secret.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/common.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> <namespace context>}
NS_CONTEXT=${2:?usage: $0 <argo context> <namespace context>}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
NS=$(context_namespace "$NS_CONTEXT")
[[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"
[[ -n $NS ]] || die "Context $NS_CONTEXT has no namespace: see README.md"

echo "Removing the test Application $TEST_APP, if any."
kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" delete application "$TEST_APP" --ignore-not-found

if kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application "$APP" >/dev/null 2>&1; then
  echo "Removing the Application $APP; Argo CD prunes the cluster and the add-ons."
  # --wait=false: the finalizer holds the Application while the cluster is
  # deleted, which takes minutes. Watch the cluster instead.
  kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" delete application "$APP" --ignore-not-found --wait=false
  wait_for "Cluster: $CLUSTER gone" 1800 cluster_gone
fi

echo "Removing the Argo CD targets."
delete_tmpl argocd/managedentity-cluster.yaml
delete_tmpl argocd/managedentity-namespace.yaml

echo "The lab is back at the start. The namespace $NS is untouched."
