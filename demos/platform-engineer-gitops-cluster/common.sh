# Shared by this demo's scripts. Not run on its own.
#
# No Terraform: the scripts kubectl-apply the Argo CD Application and the
# ManagedEntity objects straight into Argo CD's namespace, and Argo CD
# builds the cluster and its add-ons from git. Needs kubectl and jq, and a
# vcf context for the Supervisor Namespace where Argo CD runs
# (platform-<suffix>) and one for the Supervisor Namespace the cluster goes
# in.
#
# context_namespace and wait_for come from the shared lib; the GitHub
# helpers there are not used.

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
. "$here/../lib/github.sh"

# What the manifests are filled with. Override from the environment.
REPO_URL=${REPO_URL:-git@github.com:modern-apps-5/the-goad.git}
REVISION=${REVISION:-main}
PROJECT=${PROJECT:-default-project}

# Fixed names this demo uses.
GITOPS_PATH=demos/platform-engineer-gitops-cluster/gitops
TEST_PATH=demos/platform-engineer-gitops-cluster/test/manifests
APP=vks-addons                 # Application A: the cluster and its add-ons
TEST_APP=vks-addons-test       # Application B: the test workload in the cluster
NS_ENTITY=vks-addons-ns        # ManagedEntity + Argo CD destination for the namespace
CLUSTER_ENTITY=vks-addons-cluster  # ManagedEntity + Argo CD destination for the cluster
CLUSTER=pe-gitops-cluster      # the Cluster's name, from gitops/cluster.yaml

die() { echo "$1" >&2; exit "${2:-2}"; }

# Fill a template from this folder with the current values and print it.
render() {
  sed -e "s|__ARGO_NS__|${ARGO_NS:-}|g" \
      -e "s|__NAMESPACE__|${NS:-}|g" \
      -e "s|__PROJECT__|$PROJECT|g" \
      -e "s|__REPO_URL__|$REPO_URL|g" \
      -e "s|__REVISION__|$REVISION|g" \
      "$here/$1"
}

# Render a template and apply it into Argo CD's namespace.
apply_tmpl() { render "$1" | kubectl --context "$ARGO_CONTEXT" apply -f -; }

# Delete what a template defines, if it is there.
delete_tmpl() { render "$1" | kubectl --context "$ARGO_CONTEXT" delete --ignore-not-found -f - ; }

# True when an Argo CD Application is Synced and Healthy.
app_ready() {
  kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application "$1" -o json 2>/dev/null |
    jq -e '.status.sync.status == "Synced" and .status.health.status == "Healthy"' >/dev/null
}

# True when the Cluster is gone from the namespace.
cluster_gone() {
  local out
  out=$(kubectl --context "$NS_CONTEXT" -n "$NS" get cluster "$CLUSTER" --ignore-not-found -o name) &&
    [[ -z $out ]]
}

# Stop early if an add-on file still has a placeholder release.
check_releases() {
  if grep -l RELEASE_FROM_LAB "$here"/gitops/*.yaml 2>/dev/null; then
    die "These files have no release yet: see README.md."
  fi
}
