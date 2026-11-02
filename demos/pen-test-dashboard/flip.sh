#!/usr/bin/env bash
# Turn the music store's default deny off and on, to show the board "Pen
# test" change in a demo.
#
#   demos/pen-test-dashboard/flip.sh <context> off      drop the default deny
#   demos/pen-test-dashboard/flip.sh <context> on       put it back
#   demos/pen-test-dashboard/flip.sh <context> status   what is set, and the checks
#
#   demos/pen-test-dashboard/flip.sh goad:platform-9pq9n:default-project off
#
# <context> is your vcf context for the Supervisor Namespace where Argo CD
# runs, the one named platform-<suffix>. demos/pen-test-dashboard/README.md says how
# to make it.
#
# The default deny is the ClusterNetworkPolicy music-store-default-deny in
# gitops/music-store-platform/network-policy.yaml (layer 3, decision 49).
# Argo CD syncs it with self-heal on, so deleting it with kubectl would be
# undone within seconds. Argo CD is not paused. Instead, "off" adds a
# kustomize patch to the Application music-store-platform that deletes
# the policy from the rendered manifests, and Argo CD prunes it. "on"
# removes the patch, and Argo CD creates the policy again. The Application
# stays Synced throughout, and nothing else in it changes.
#
# With the default deny off, pen test checks 1 and 2 (the store pod and its
# Service, around Avi) reach the store and turn red. The WAF checks do not
# change. The script waits for Argo CD, then for the checks, which the
# blackbox exporter runs every 30 seconds.
#
# The patch is drift from the platform engineer's Terraform, which owns the
# Application. A platform engineer apply while it is off turns the default
# deny back on. Run "on" after the demo.
#
# Needs kubectl, curl and jq, and the right to patch Argo CD Applications
# in that namespace, which the platform engineers' group has. The
# namespace is the context's own; set NAMESPACE only for a context that
# points elsewhere.
set -euo pipefail

usage() { echo "usage: $0 <context> off|on|status" >&2; exit 2; }
CONTEXT=${1:-}
ACTION=${2:-}
[[ -n $CONTEXT ]] || usage
case $ACTION in off | on | status) ;; *) usage ;; esac

APP=music-store-platform
POLICY=music-store-default-deny
PROMETHEUS=${PROMETHEUS:-http://prometheus.goad.gpu.set.lab}
NAMESPACE=${NAMESPACE:-$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$CONTEXT\")].context.namespace}")}
[[ -n $NAMESPACE ]] || { echo "Context $CONTEXT has no namespace. Use the context of the platform-<suffix> namespace (see demos/pen-test-dashboard/README.md), or set NAMESPACE" >&2; exit 2; }

k() { kubectl --context "$CONTEXT" -n "$NAMESPACE" "$@"; }

app_json() { k get application "$APP" -o json; }

# The index of our patch in the Application's kustomize patches, or empty.
patch_index() {
  app_json | jq -r --arg name "$POLICY" '
    [.spec.source.kustomize.patches // [] | to_entries[]
      | select(.value.target.kind == "ClusterNetworkPolicy" and .value.target.name == $name)
      | .key][0] // empty'
}

# "present" when Argo CD lists the policy as one of the Application's
# resources, "absent" when not.
policy_state() {
  app_json | jq -r --arg name "$POLICY" '
    if any(.status.resources[]?; .kind == "ClusterNetworkPolicy" and .name == $name)
    then "present" else "absent" end'
}

# The five checks, from the recording rule pen_test_pass: 1 is a pass.
checks() {
  curl -sf -m 10 "$PROMETHEUS/api/v1/query" --data-urlencode 'query=pen_test_pass' |
    jq -r '.data.result[] | "\(.metric.pen_test)=\(.value[1])"' | sort | tr '\n' ' '
}

show_status() {
  local app idx
  app=$(app_json)
  idx=$(patch_index)
  echo "Argo CD:        $(jq -r '"\(.status.sync.status), \(.status.health.status)"' <<<"$app")"
  echo "Default deny:   $(policy_state)$([[ -n $idx ]] && echo ', turned off by flip.sh')"
  echo "Pen test:       $(checks || echo 'Prometheus not reachable')"
  echo "                (1 = pass; pod and service fail while the default deny is off)"
}

# Waits until fn prints want, for up to limit seconds.
wait_for() {
  local what=$1 want=$2 limit=$3 fn=$4 start=$SECONDS got
  printf '%s' "$what"
  while :; do
    got=$($fn 2>/dev/null || true)
    if [[ $got == "$want" ]]; then echo " done ($((SECONDS - start))s)"; return 0; fi
    if ((SECONDS - start >= limit)); then echo " still $got after ${limit}s"; return 1; fi
    printf '.'
    sleep 5
  done
}

# "pass" or "fail" for the two checks around Avi, "mixed" between.
around_avi() {
  local c
  c=$(checks)
  case $c in
    *pod=1*service=1* | *service=1*pod=1*) echo pass ;;
    *pod=0*service=0* | *service=0*pod=0*) echo fail ;;
    *) echo mixed ;;
  esac
}

case $ACTION in
  status)
    show_status
    ;;
  off)
    if [[ -n $(patch_index) ]]; then
      echo "The default deny is already off."
    else
      patch=$(jq -cn --arg name "$POLICY" '[{
        op: "add", path: "/spec/source/kustomize/patches/-",
        value: {
          target: {group: "crd.antrea.io", kind: "ClusterNetworkPolicy", name: $name},
          patch: "$patch: delete\napiVersion: crd.antrea.io/v1beta1\nkind: ClusterNetworkPolicy\nmetadata:\n  name: \($name)\n"
        }}]')
      k patch application "$APP" --type json -p "$patch" >/dev/null
      echo "Patched Application $APP to drop $POLICY."
    fi
    wait_for "Argo CD pruning the policy" absent 180 policy_state
    wait_for "Pen test checks 1 and 2 failing" fail 120 around_avi
    show_status
    ;;
  on)
    idx=$(patch_index)
    if [[ -z $idx ]]; then
      echo "The default deny is already on."
    else
      # The test op stops the remove if the patches moved since the read.
      patch=$(jq -cn --argjson i "$idx" --arg name "$POLICY" '[
        {op: "test", path: "/spec/source/kustomize/patches/\($i)/target/name", value: $name},
        {op: "remove", path: "/spec/source/kustomize/patches/\($i)"}]')
      k patch application "$APP" --type json -p "$patch" >/dev/null
      echo "Removed the patch; Argo CD puts $POLICY back."
    fi
    wait_for "Argo CD creating the policy" present 180 policy_state
    wait_for "Pen test checks 1 and 2 passing" pass 120 around_avi
    show_status
    ;;
esac
