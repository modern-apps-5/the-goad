#!/usr/bin/env bash
# Turn the music store's security layers off and on, to show the board
# "Pen test" change in a demo.
#
#   demos/pen-test-dashboard/flip.sh <context> off [layer]   take the layer out
#   demos/pen-test-dashboard/flip.sh <context> on [layer]    put it back
#   demos/pen-test-dashboard/flip.sh <context> status        what is set, and the checks
#
#   demos/pen-test-dashboard/flip.sh goad:platform-9pq9n:default-project off
#   demos/pen-test-dashboard/flip.sh goad:platform-9pq9n:default-project off all
#
# <context> is your vcf context for the Supervisor Namespace where Argo CD
# runs, the one named platform-<suffix>. demos/pen-test-dashboard/README.md
# says how to make it.
#
# [layer] is one of:
#
#   deny  the default deny, the ClusterNetworkPolicy music-store-default-deny
#         in gitops/music-store-platform (layer 3, decision 49). Off: pen
#         test checks 1 and 2, around Avi, reach the store. The default.
#   waf   the Avi WAF, the L7Rule metal-store-waf and the HTTPRoute filter
#         that attaches it, in gitops/music-store-apps (decision 43). Off:
#         checks 3 and 4, the injections through Avi, answer 200.
#   all   both.
#
# Argo CD syncs these with self-heal on, so deleting them with kubectl
# would be undone within seconds. Argo CD is not paused. Instead, "off"
# adds kustomize patches to the layer's Application that take the layer
# out of the rendered manifests, and Argo CD prunes or updates them. "on"
# removes the patches, and Argo CD puts the layer back. The Applications
# stay Synced throughout, and nothing else in them changes.
#
# The script waits for Argo CD, then for the checks, which the blackbox
# exporter runs every 30 seconds.
#
# The patches are drift from the platform engineer's Terraform, which owns
# the Applications. A platform engineer apply while a layer is off puts it
# back. Run "on all" after the demo.
#
# Needs kubectl, curl and jq, and the right to patch Argo CD Applications
# in that namespace. The namespace is the context's own; set NAMESPACE
# only for a context that points elsewhere.
set -euo pipefail

usage() { echo "usage: $0 <context> off|on [deny|waf|all] | status" >&2; exit 2; }
CONTEXT=${1:-}
ACTION=${2:-}
LAYER=${3:-deny}
[[ -n $CONTEXT ]] || usage
case $ACTION in off | on | status) ;; *) usage ;; esac
case $LAYER in deny | waf | all) ;; *) usage ;; esac

PROMETHEUS=${PROMETHEUS:-http://prometheus.goad.gpu.set.lab}
NAMESPACE=${NAMESPACE:-$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$CONTEXT\")].context.namespace}")}
[[ -n $NAMESPACE ]] || { echo "Context $CONTEXT has no namespace. Use the context of the platform-<suffix> namespace (see demos/pen-test-dashboard/README.md), or set NAMESPACE" >&2; exit 2; }

k() { kubectl --context "$CONTEXT" -n "$NAMESPACE" "$@"; }

# Each layer: its name, its Application, the resource whose presence says
# whether it is on, the pen test checks it decides, and the patches that
# take it out. The patches are found again by their targets.
layer_name() { case $1 in deny) echo "Default deny" ;; waf) echo "Avi WAF" ;; esac; }
layer_app() { case $1 in deny) echo music-store-platform ;; waf) echo music-store-apps ;; esac; }
layer_marker() { case $1 in deny) echo ClusterNetworkPolicy/music-store-default-deny ;; waf) echo L7Rule/metal-store-waf ;; esac; }
layer_checks() { case $1 in deny) echo "pod service" ;; waf) echo "sqli phpi" ;; esac; }
layer_patches() {
  case $1 in
    deny)
      jq -cn '[{
        target: {group: "crd.antrea.io", kind: "ClusterNetworkPolicy", name: "music-store-default-deny"},
        patch: "$patch: delete\napiVersion: crd.antrea.io/v1beta1\nkind: ClusterNetworkPolicy\nmetadata:\n  name: music-store-default-deny\n"
      }]'
      ;;
    waf)
      # The route names the L7Rule in an ExtensionRef filter, so the filter
      # goes with it.
      jq -cn '[{
        target: {group: "ako.vmware.com", kind: "L7Rule", name: "metal-store-waf"},
        patch: "$patch: delete\napiVersion: ako.vmware.com/v1alpha2\nkind: L7Rule\nmetadata:\n  name: metal-store-waf\n"
      }, {
        target: {group: "gateway.networking.k8s.io", kind: "HTTPRoute", name: "metal-store-frontend"},
        patch: "- op: remove\n  path: /spec/rules/0/filters\n"
      }]'
      ;;
  esac
}

layers() { if [[ $1 == all ]]; then echo deny waf; else echo "$1"; fi; }

app_json() { k get application "$(layer_app "$1")" -o json; }

# The indexes of the layer's patches in its Application, highest first.
patch_indexes() {
  app_json "$1" | jq -r --argjson ours "$(layer_patches "$1")" '
    [.spec.source.kustomize.patches // [] | to_entries[]
      | select(.value.target as $t | any($ours[]; .target == $t))
      | .key] | sort | reverse | .[]'
}

# "present" when Argo CD lists the layer's marker resource, else "absent".
layer_state() {
  local kind=${2:-} name
  kind=$(layer_marker "$1"); name=${kind#*/}; kind=${kind%/*}
  app_json "$1" | jq -r --arg kind "$kind" --arg name "$name" '
    if any(.status.resources[]?; .kind == $kind and .name == $name)
    then "present" else "absent" end'
}

# The checks, from the recording rule pen_test_pass: 1 is a pass.
checks() {
  curl -sf -m 10 "$PROMETHEUS/api/v1/query" --data-urlencode 'query=pen_test_pass' |
    jq -r '.data.result[] | "\(.metric.pen_test)=\(.value[1])"' | sort | tr '\n' ' '
}

# "pass" or "fail" when every check the layer decides is that, else "mixed".
checks_state() {
  local c n want=() got
  c=" $(checks) "
  for n in $(layer_checks "$1"); do
    case $c in *" $n=1 "*) want+=(pass) ;; *" $n=0 "*) want+=(fail) ;; *) want+=(none) ;; esac
  done
  got=$(printf '%s\n' "${want[@]}" | sort -u)
  [[ $got == pass || $got == fail ]] && echo "$got" || echo mixed
}

show_status() {
  local l app
  for l in deny waf; do
    app=$(app_json "$l")
    printf '%-15s %s; Application %s %s, %s%s\n' "$(layer_name "$l"):" "$(layer_state "$l")" \
      "$(layer_app "$l")" \
      "$(jq -r .status.sync.status <<<"$app")" "$(jq -r .status.health.status <<<"$app")" \
      "$([[ -n $(patch_indexes "$l") ]] && echo ', turned off by flip.sh')"
  done
  echo "Pen test:       $(checks || echo 'Prometheus not reachable')"
  echo "                (1 = pass; pod and service fail while the default deny is off,"
  echo "                sqli and phpi while the WAF is off)"
}

# Waits until "fn arg" prints want, for up to limit seconds.
wait_for() {
  local what=$1 want=$2 limit=$3 fn=$4 arg=$5 start=$SECONDS got
  printf '%s' "$what"
  while :; do
    got=$($fn "$arg" 2>/dev/null || true)
    if [[ $got == "$want" ]]; then echo " done ($((SECONDS - start))s)"; return 0; fi
    if ((SECONDS - start >= limit)); then echo " still $got after ${limit}s"; return 1; fi
    printf '.'
    sleep 5
  done
}

turn_off() {
  local l=$1 patch
  if [[ -n $(patch_indexes "$l") ]]; then
    echo "$(layer_name "$l") is already off."
    return
  fi
  patch=$(layer_patches "$l" | jq -c '[.[] | {op: "add", path: "/spec/source/kustomize/patches/-", value: .}]')
  k patch application "$(layer_app "$l")" --type json -p "$patch" >/dev/null
  echo "$(layer_name "$l"): patched Application $(layer_app "$l") to take it out."
}

turn_on() {
  local l=$1 idx patch='[]'
  idx=$(patch_indexes "$l")
  if [[ -z $idx ]]; then
    echo "$(layer_name "$l") is already on."
    return
  fi
  # Highest index first, so each remove leaves the others in place. The
  # test ops stop the patch if the list moved since the read.
  for i in $idx; do
    patch=$(app_json "$l" | jq -c --argjson p "$patch" --argjson i "$i" \
      '$p + [{op: "test", path: "/spec/source/kustomize/patches/\($i)", value: .spec.source.kustomize.patches[$i]},
             {op: "remove", path: "/spec/source/kustomize/patches/\($i)"}]')
  done
  k patch application "$(layer_app "$l")" --type json -p "$patch" >/dev/null
  echo "$(layer_name "$l"): removed the patches; Argo CD puts it back."
}

case $ACTION in
  status)
    show_status
    ;;
  off | on)
    for l in $(layers "$LAYER"); do
      if [[ $ACTION == off ]]; then turn_off "$l"; else turn_on "$l"; fi
    done
    for l in $(layers "$LAYER"); do
      if [[ $ACTION == off ]]; then
        wait_for "$(layer_name "$l"): Argo CD taking it out" absent 180 layer_state "$l"
        wait_for "$(layer_name "$l"): pen test checks $(layer_checks "$l") failing" fail 180 checks_state "$l"
      else
        wait_for "$(layer_name "$l"): Argo CD putting it back" present 180 layer_state "$l"
        wait_for "$(layer_name "$l"): pen test checks $(layer_checks "$l") passing" pass 180 checks_state "$l"
      fi
    done
    show_status
    ;;
esac
