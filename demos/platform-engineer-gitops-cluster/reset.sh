#!/usr/bin/env bash
# Put the lab back after the demo: the cluster, its add-ons and the
# namespace vks-addons gone, the same way the demo made them.
#
#   demos/platform-engineer-gitops-cluster/reset.sh <argo context> <cluster context>
#
# The contexts are the same as status.sh's.
#
# It takes two pull requests. The first removes the cluster and the
# add-ons from git, and Argo CD prunes them. keep.yaml stays until that is
# done: Argo CD does not prune when git has nothing left for an
# Application. The second removes the rest and the namespace, and the
# workflow platform-engineer applies that. What is already gone is
# skipped, so it can run again after a failure.
#
# Needs gh, kubectl, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> <cluster context>}
CLUSTER_CONTEXT=${2:?usage: $0 <argo context> <cluster context>}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
CLUSTER_NS=$(context_namespace "$CLUSTER_CONTEXT")
[[ -n $ARGO_NS && -n $CLUSTER_NS ]] || { echo "Both contexts must point at a namespace: see README.md" >&2; exit 2; }

if on_main gitops/vks-addons/cluster.yaml; then
  branch=demo-gitops-cluster-prune-$(date +%Y%m%d%H%M%S)
  new_branch "$branch"
  for path in $(gh api "repos/$REPO/contents/gitops/vks-addons?ref=main" --jq '.[].path'); do
    [[ $path == */keep.yaml ]] || delete_file "$branch" "$path" "Remove $path"
  done
  merge_branch "$branch" "Demo: remove the VKS cluster vks-addons" \
    "Argo CD prunes the cluster and its add-ons. Opened by demos/platform-engineer-gitops-cluster/reset.sh."
fi

app=$(kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application vks-addons --ignore-not-found -o name)
if [[ -n $app ]]; then
  # --ignore-not-found, so an expired session is a failure and not "gone".
  cluster_gone() {
    local cluster
    cluster=$(kubectl --context "$CLUSTER_CONTEXT" -n "$CLUSTER_NS" get cluster vks-addons --ignore-not-found -o name) &&
      [[ -z $cluster ]]
  }
  wait_for "Cluster: vks-addons gone" 1800 cluster_gone
fi

if on_main gitops/vks-addons/keep.yaml; then
  branch=demo-gitops-cluster-reset-$(date +%Y%m%d%H%M%S)
  new_branch "$branch"
  delete_file "$branch" gitops/vks-addons/keep.yaml "Remove gitops/vks-addons"
  edit_file "$branch" terraform/platform-engineer/variables.tf \
    's/    # Made and removed by demos\/platform-engineer-gitops-cluster\.\n    vks-addons = \{.*?\n    \}\n//s' \
    "Remove the Supervisor Namespace vks-addons" || [[ $? == 3 ]]
  merge_branch "$branch" "Demo: remove the namespace vks-addons" \
    "After the VKS add-ons demo. Opened by demos/platform-engineer-gitops-cluster/reset.sh."
fi

echo "Applying terraform/platform-engineer."
run_workflow platform-engineer.yml -f apply=true
plan_summary "$RUN_ID" || true
echo "The lab is back at the start."
