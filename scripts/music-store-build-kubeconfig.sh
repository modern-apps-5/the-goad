#!/usr/bin/env bash
# Store the kubeconfig the music store's image build starts Tekton with.
#
#   scripts/music-store-build-kubeconfig.sh <Supervisor Namespace context>
#   scripts/music-store-build-kubeconfig.sh goad-pe:platform-tools-jb937:default-project
#
# The workflow .github/workflows/music-store-images.yml starts a
# PipelineRun on the platform tools cluster as the ServiceAccount
# pipeline-starter in music-store-builds (gitops/platform-tools-builds).
# Its token is made in the cluster. This reads it, with the cluster's
# address and CA, writes a kubeconfig that holds only that, and stores it
# as the GitHub secret MUSIC_STORE_BUILD_KUBECONFIG. Nothing is printed.
#
# Run it once after Argo CD has synced platform-tools-builds, and again if
# the cluster or the token is made again.
#
# Needs kubectl, a vcf context for the platform tools cluster's Supervisor
# Namespace (the platform engineer's), and gh, logged in with access to
# the repository's secrets.
set -euo pipefail

CONTEXT=${1:?usage: $0 <vcf context of the platform-tools Supervisor Namespace>}
CLUSTER=platform-tools
NAMESPACE=music-store-builds
REPO=${REPO:-modern-apps-5/the-goad}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
umask 077

# The cluster's admin kubeconfig, from its Supervisor Namespace. Used only
# here, to read the token.
kubectl --context "$CONTEXT" get secret "$CLUSTER-kubeconfig" \
  -o jsonpath='{.data.value}' | base64 -d > "$WORK/admin"

server=$(kubectl --kubeconfig "$WORK/admin" config view --raw -o jsonpath='{.clusters[0].cluster.server}')
kubectl --kubeconfig "$WORK/admin" -n "$NAMESPACE" get secret pipeline-starter-token \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > "$WORK/ca.crt"
token=$(kubectl --kubeconfig "$WORK/admin" -n "$NAMESPACE" get secret pipeline-starter-token \
  -o jsonpath='{.data.token}' | base64 -d)
[[ -n $token ]] || { echo "pipeline-starter-token has no token yet" >&2; exit 1; }

kc="$WORK/build"
kubectl --kubeconfig "$kc" config set-cluster "$CLUSTER" --server "$server" \
  --certificate-authority "$WORK/ca.crt" --embed-certs >/dev/null
kubectl --kubeconfig "$kc" config set-credentials pipeline-starter --token "$token" >/dev/null
kubectl --kubeconfig "$kc" config set-context build --cluster "$CLUSTER" \
  --user pipeline-starter --namespace "$NAMESPACE" >/dev/null
kubectl --kubeconfig "$kc" config use-context build >/dev/null

# Prove the login before storing it.
kubectl --kubeconfig "$kc" auth can-i create pipelineruns.tekton.dev -n "$NAMESPACE" >/dev/null

gh secret set MUSIC_STORE_BUILD_KUBECONFIG -R "$REPO" < "$kc"
echo "MUSIC_STORE_BUILD_KUBECONFIG set for $REPO."
