#!/usr/bin/env bash
# Make the GOAD CA, store its key as a GitHub secret, and write its
# certificate where git needs it.
#
#   scripts/goad-ca.sh            make the CA, once
#   scripts/goad-ca.sh --rotate   make a new one in place of the old
#
# The CA signs the certificates of GOAD's own names, in goad.gpu.set.lab,
# starting with Private AI Services (gitops/private-ai/ingress.yaml). The
# lab has no public CA. The key goes only to the GitHub secret
# GOAD_CA_KEY, in the environment lab: the platform engineer Terraform
# writes it into the Secret goad-ca in the private-ai Supervisor
# Namespace, and cert-manager issues from it there. The certificate is
# public and is written to:
#
#   gitops/private-ai/goad-ca.crt                     the copy Terraform reads
#   gitops/private-ai/goad-ca-pkiprofile.yaml         Avi trusts PAIS with it
#   gitops/music-store-apps/goad-ca.crt               the shop's chat trusts it
#   tanzu/metal-music-app-agentic-system/shared/trust/goad-ca.pem
#                                                     the incident agents trust it
#
# Commit those files, then run the platform engineer workflow. With
# KEY_OUT=<file>, the key is also written there, for terraform.tfvars on a
# machine (goad_ca_key). Nothing secret is printed.
#
# Needs openssl and gh, logged in with access to the environment's secrets.
set -euo pipefail

REPO=${REPO:-modern-apps-5/the-goad}
ENVIRONMENT=${ENVIRONMENT:-lab}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CERT=$ROOT/gitops/private-ai/goad-ca.crt

if [ -e "$CERT" ] && [ "${1:-}" != "--rotate" ]; then
  echo "$CERT exists. Use --rotate to replace the CA; every client must then trust the new one." >&2
  exit 1
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
umask 077

openssl req -x509 -new -newkey rsa:3072 -nodes -sha256 -days 3650 \
  -subj "/O=GOAD/CN=GOAD CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout "$WORK/ca.key" -out "$WORK/ca.crt" 2>/dev/null

gh secret set GOAD_CA_KEY -R "$REPO" -e "$ENVIRONMENT" < "$WORK/ca.key"
if [ -n "${KEY_OUT:-}" ]; then
  cp "$WORK/ca.key" "$KEY_OUT"
fi

umask 022
cp "$WORK/ca.crt" "$CERT"
cp "$WORK/ca.crt" "$ROOT/gitops/music-store-apps/goad-ca.crt"
cp "$WORK/ca.crt" "$ROOT/tanzu/metal-music-app-agentic-system/shared/trust/goad-ca.pem"
{
  cat << 'EOF'
# Avi's trust for the PAIS ingress certificate: the GOAD CA. Written by
# scripts/goad-ca.sh; do not edit. The RouteBackendExtension pais in
# ingress.yaml names it.
apiVersion: ako.vmware.com/v1alpha1
kind: PKIProfile
metadata:
  name: goad-ca
  annotations:
    argocd.argoproj.io/sync-wave: "3"
spec:
  ca_certs:
    - certificate: |
EOF
  sed 's/^/        /' "$WORK/ca.crt"
} > "$ROOT/gitops/private-ai/goad-ca-pkiprofile.yaml"

openssl x509 -in "$CERT" -noout -subject -enddate
echo "Stored GOAD_CA_KEY in $REPO, environment $ENVIRONMENT. Commit the certificate files listed in $0."
