#!/usr/bin/env bash
# Build the demo's VKS cluster and add-ons from git with Argo CD, then
# register the cluster as an Argo CD target. No Terraform.
#
#   demos/platform-engineer-gitops-cluster/deploy.sh <argo context> <namespace context> [git ref]
#
# <argo context>      vcf context for the Supervisor Namespace where Argo CD
#                     runs, platform-<suffix>.
# <namespace context> vcf context for the existing Supervisor Namespace the
#                     cluster goes in. Reused, not created: see README.md.
# [git ref]           the revision Argo CD reads the manifests from
#                     (default main). Use your branch while testing, once it
#                     is pushed.
#
# It kubectl-applies, into Argo CD's namespace:
#   1. a ManagedEntity that registers the namespace as a destination;
#   2. the Application that builds the cluster and its add-ons, then waits
#      for it to be Healthy;
#   3. a ManagedEntity that registers the cluster as a target.
# Each step is idempotent, so it can run again after a failure.
#
# Needs kubectl and jq. Prints no secret.
set -euo pipefail
. "$(cd "$(dirname "$0")" && pwd)/common.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context> <namespace context> [git ref]}
NS_CONTEXT=${2:?usage: $0 <argo context> <namespace context> [git ref]}
REVISION=${3:-$REVISION}

ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
NS=$(context_namespace "$NS_CONTEXT")
[[ -n $ARGO_NS ]] || die "Context $ARGO_CONTEXT has no namespace: see README.md"
[[ -n $NS ]] || die "Context $NS_CONTEXT has no namespace: see README.md"
check_releases

echo "Namespace $NS: registering it as an Argo CD destination (ManagedEntity $NS_ENTITY)."
apply_tmpl argocd/managedentity-namespace.yaml

echo "Application $APP: building the cluster $CLUSTER and its add-ons from $REVISION."
apply_tmpl argocd/application.yaml

wait_for "Argo CD: $APP Synced and Healthy" 2400 app_ready "$APP"

echo "Cluster $CLUSTER: registering it as an Argo CD target (ManagedEntity $CLUSTER_ENTITY)."
apply_tmpl argocd/managedentity-cluster.yaml

cat <<EOF

Done. The cluster $CLUSTER is built and registered with Argo CD.
  - See the destinations in Argo CD: Settings, Clusters, $NS_ENTITY and $CLUSTER_ENTITY.
  - Where it stands:  demos/platform-engineer-gitops-cluster/status.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
  - Test the target:  demos/platform-engineer-gitops-cluster/test-app.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
EOF
