#!/usr/bin/env bash
# Build the demo's VKS cluster from git: one pull request, one Terraform
# run, and then Argo CD.
#
#   demos/platform-engineer-gitops-cluster/deploy.sh <argo context>
#
# <argo context> is your vcf context for the Supervisor Namespace
# platform-<suffix>, where Argo CD runs: see README.md.
#
# The pull request adds the namespace vks-addons to
# terraform/platform-engineer/variables.tf, and the manifests in gitops/
# here to gitops/vks-addons on main. It merges it, runs the workflow
# platform-engineer with apply, and waits for Argo CD to report the
# cluster Healthy. What is already done is skipped, so it can run again
# after a failure.
#
# Needs gh, kubectl, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context>}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || { echo "Context $ARGO_CONTEXT has no namespace: see README.md" >&2; exit 2; }

if grep -l RELEASE_FROM_LAB "$here"/gitops/*.yaml; then
  echo "These files have no release yet: see README.md." >&2
  exit 2
fi

# The perl in edit_file reads this from its environment.
export NAMESPACE_ENTRY='    # Made and removed by demos/platform-engineer-gitops-cluster.
    vks-addons = {
      description   = "GOAD VKS add-ons demo: a VKS cluster managed by Argo CD. Managed by terraform/platform-engineer."
      cpu_limit     = "40000M"
      memory_limit  = "48Gi"
      storage_limit = "150Gi"
    }
'

if on_main gitops/vks-addons/cluster.yaml; then
  echo "gitops/vks-addons is already on main."
else
  branch=demo-gitops-cluster-$(date +%Y%m%d%H%M%S)
  new_branch "$branch"
  edit_file "$branch" terraform/platform-engineer/variables.tf \
    's/(    platform-tools = \{.*?\n    \}\n)/$1$ENV{NAMESPACE_ENTRY}/s' \
    "Add the Supervisor Namespace vks-addons"
  for file in "$here"/gitops/*.yaml; do
    add_file "$branch" "gitops/vks-addons/$(basename "$file")" "$file" \
      "Add $(basename "$file") to gitops/vks-addons"
  done
  merge_branch "$branch" "Demo: a VKS cluster with add-ons, managed by Argo CD" \
    "The namespace vks-addons, and its VKS cluster with Headlamp and cert-manager, and the platform-observability label for Prometheus and Telegraf. Opened by demos/platform-engineer-gitops-cluster/deploy.sh."
fi

echo "Applying terraform/platform-engineer."
run_workflow platform-engineer.yml -f apply=true
plan_summary "$RUN_ID" || true

app_ready() {
  kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application vks-addons -o json |
    jq -e '.status.sync.status == "Synced" and .status.health.status == "Healthy"'
}
wait_for "Argo CD: vks-addons Synced and Healthy" 2400 app_ready

namespace=$(kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application vks-addons -o jsonpath='{.spec.destination.namespace}')
echo "The cluster vks-addons is ready, in the Supervisor Namespace $namespace."
