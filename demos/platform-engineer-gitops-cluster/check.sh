#!/usr/bin/env bash
# Check the lab before the demo: every add-on has a release, the demo is
# not on main or in Argo CD, and the platform engineer's Terraform plans
# no change.
#
#   demos/platform-engineer-gitops-cluster/check.sh <argo context>
#
# <argo context> is your vcf context for the Supervisor Namespace
# platform-<suffix>, where Argo CD runs: see README.md. It starts the
# workflow platform-engineer as a plan only, so it takes a few minutes. It
# changes nothing.
#
# Needs gh, kubectl and jq. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

ARGO_CONTEXT=${1:?usage: $0 <argo context>}
ARGO_NS=$(context_namespace "$ARGO_CONTEXT")
[[ -n $ARGO_NS ]] || { echo "Context $ARGO_CONTEXT has no namespace: see README.md" >&2; exit 2; }

ok=true

if grep -l RELEASE_FROM_LAB "$here"/gitops/*.yaml; then
  ok=false
  echo "These files have no release yet: see README.md."
fi

if on_main gitops/vks-addons; then
  ok=false
  echo "gitops/vks-addons is on main: run reset.sh."
fi

app=$(kubectl --context "$ARGO_CONTEXT" -n "$ARGO_NS" get application vks-addons --ignore-not-found -o name)
if [[ -n $app ]]; then
  ok=false
  echo "Application vks-addons exists: run reset.sh."
fi

echo "Planning terraform/platform-engineer, without apply."
run_workflow platform-engineer.yml -f apply=false
plan_summary "$RUN_ID" || { ok=false; echo "The plan has changes. Find out whose they are before the demo."; }

echo
$ok && echo "Ready for the demo." || { echo "Not ready."; exit 1; }
