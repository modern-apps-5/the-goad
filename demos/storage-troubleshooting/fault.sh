#!/usr/bin/env bash
# Start or end the storage fault in the storage troubleshooting demo.
#
#   demos/storage-troubleshooting/fault.sh <store context> start
#   demos/storage-troubleshooting/fault.sh <store context> stop
#   demos/storage-troubleshooting/fault.sh <store context> status
#
# start moves the vSAN disks behind the shop's cart-pvc and order-pvc to a
# storage policy with a low IOPS limit, then starts the shoppers
# (shoppers.yaml) in the music store cluster. stop deletes the shoppers and
# moves the disks back to their StorageClass's policy. status prints each
# disk's policy and the shoppers' last requests.
#
# <store context> is your vcf context for the Supervisor Namespace
# music-store-<suffix>: see README.md. The script reads the cluster's
# kubeconfig from that namespace into a temporary file, and deletes it when
# it ends. Your own kubectl contexts are not changed.
#
# VC_HOST and VC_USER name your vCenter login; VC_PASSWORD is asked for if
# not set. IOPS_LIMIT sets the cap (10 unless set).
#
# Needs kubectl and uv. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

usage() { echo "usage: $0 <store context> start|stop|status" >&2; exit 2; }
CONTEXT=${1:-}
ACTION=${2:-}
[[ -n $CONTEXT ]] || usage
case $ACTION in start | stop | status) ;; *) usage ;; esac
[[ -n ${VC_HOST:-} && -n ${VC_USER:-} ]] || { echo "Set VC_HOST and VC_USER to your vCenter login first." >&2; exit 2; }

NAMESPACE=$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$CONTEXT\")].context.namespace}")
[[ -n $NAMESPACE ]] || { echo "Context $CONTEXT has no namespace: see README.md" >&2; exit 2; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
umask 077
kubectl --context "$CONTEXT" -n "$NAMESPACE" get secret music-store-kubeconfig \
  -o jsonpath='{.data.value}' | base64 -d > "$WORK/kubeconfig"
store() { kubectl --kubeconfig "$WORK/kubeconfig" "$@"; }

# A VKS PVC is backed by a PVC in the Supervisor Namespace, named by the
# guest PV's volume handle. That PVC's volume is the CNS disk in vCenter.
volumes=()
for claim in cart-pvc order-pvc; do
  pv=$(store -n music-store get pvc "$claim" -o jsonpath='{.spec.volumeName}')
  handle=$(store get pv "$pv" -o jsonpath='{.spec.csi.volumeHandle}')
  volumes+=("$(kubectl --context "$CONTEXT" -n "$NAMESPACE" get pvc "$handle" -o jsonpath='{.spec.volumeName}')")
  STORAGE_CLASS=$(kubectl --context "$CONTEXT" -n "$NAMESPACE" get pvc "$handle" -o jsonpath='{.spec.storageClassName}')
done
export STORAGE_CLASS

case $ACTION in
  start)
    uv run -q "$here/fault.py" start "$NAMESPACE" "${volumes[@]}"
    store apply -f "$here/shoppers.yaml"
    store -n shoppers rollout status deploy/shoppers --timeout=120s
    ;;
  stop)
    store delete -f "$here/shoppers.yaml" --ignore-not-found --wait=false
    uv run -q "$here/fault.py" stop "$NAMESPACE" "${volumes[@]}"
    ;;
  status)
    uv run -q "$here/fault.py" status "$NAMESPACE" "${volumes[@]}"
    store -n shoppers logs deploy/shoppers --tail=9 2>/dev/null || echo "No shoppers running."
    ;;
esac
