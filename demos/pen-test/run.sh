#!/usr/bin/env bash
# Run the security demo's pen test from inside the VKS cluster music-store.
#
#   demos/pen-test/run.sh            start the attacker pod if needed, run the check
#   demos/pen-test/run.sh --delete   remove the attacker pod and what it needs
#
# Extra environment is passed to the check, for example:
#   VIP=10.47.7.95 demos/pen-test/run.sh
#
# Needs kubectl with the current context on the VKS cluster music-store.
set -euo pipefail

dir=$(cd "$(dirname "$0")" && pwd)
ns=music-store

if [ "${1:-}" = "--delete" ]; then
  kubectl delete -f "$dir/attacker.yaml" --ignore-not-found
  kubectl -n "$ns" delete configmap pen-test-script --ignore-not-found
  exit 0
fi

kubectl -n "$ns" create configmap pen-test-script \
  --from-file=connectivity-check.sh="$dir/connectivity-check.sh" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$dir/attacker.yaml"
kubectl -n "$ns" wait --for=condition=Ready pod/attacker --timeout=120s

env_args=()
for name in HOST VIP SVC TGT_NS TGT_LABEL PORT SQLI PHPI TIMEOUT; do
  [ -n "${!name:-}" ] && env_args+=("$name=${!name}")
done
kubectl -n "$ns" exec -it attacker -- env "${env_args[@]}" /scripts/connectivity-check.sh
