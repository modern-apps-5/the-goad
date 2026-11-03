#!/usr/bin/env bash
# Start or end the incident the agents investigate in the agentic ops
# automation demo. start slows the music store's catalog and opens one
# Zammad ticket; stop makes the catalog fast again. Both run
# scripts/incident-walk.sh against the music store cluster.
#
#   ZAMMAD_TOKEN=... demos/agentic-ops-automation/incident.sh <store context> start
#   demos/agentic-ops-automation/incident.sh <store context> stop
#
# <store context> is your vcf context for the Supervisor Namespace
# music-store-<suffix>: see README.md. The script reads the cluster's
# kubeconfig from that namespace into a temporary file, and deletes it when
# it ends. Your own kubectl contexts are not changed.
#
# ZAMMAD_TOKEN is a Zammad API token, for start only. STORE_URL and
# ZAMMAD_URL have the lab's values unless set.
#
# Needs kubectl and python3. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)

usage() { echo "usage: $0 <store context> start|stop" >&2; exit 2; }
CONTEXT=${1:-}
ACTION=${2:-}
[[ -n $CONTEXT ]] || usage
case $ACTION in start | stop) ;; *) usage ;; esac
if [[ $ACTION == start && -z ${ZAMMAD_TOKEN:-} ]]; then
  echo "Set ZAMMAD_TOKEN to a Zammad API token first." >&2
  exit 2
fi

NAMESPACE=$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$CONTEXT\")].context.namespace}")
[[ -n $NAMESPACE ]] || { echo "Context $CONTEXT has no namespace: see README.md" >&2; exit 2; }

export STORE_URL=${STORE_URL:-https://music.goad.gpu.set.lab}
export ZAMMAD_URL=${ZAMMAD_URL:-http://zammad.goad.gpu.set.lab}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
umask 077
kubectl --context "$CONTEXT" -n "$NAMESPACE" get secret music-store-kubeconfig \
  -o jsonpath='{.data.value}' | base64 -d > "$WORK/kubeconfig"
export KUBECONFIG=$WORK/kubeconfig

"$here/../../scripts/incident-walk.sh" "$ACTION"
