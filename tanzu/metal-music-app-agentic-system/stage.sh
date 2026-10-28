#!/usr/bin/env bash
# Copy the shared files into the agent apps before cf push.
#
#   stage.sh <AgentMinder SDK wheel>
#
# tanzu-apps.yml runs this on a fresh checkout. Each app directory is pushed
# as it is; this adds only what four apps share, so it is kept once in git:
#   - the model trust (pais-root.pem, model_proxy.py, .profile) for all four
#     agents. The Goad model ingress certificate is signed by its own CA;
#   - the findings schema, next to each agent's skill;
#   - the AgentMinder sidecar, with the SDK unpacked into
#     sidecar/site-packages, and agentminder-env.sh, which reads the agent's
#     AgentMinder client from its bound am-* service, for the three
#     diagnostic agents.
# The wheel comes from ghcr.io/modern-apps-5/agentminder-sdk
# (scripts/mirror-agentminder-sdk.sh). The SDK is not on public PyPI.
set -euo pipefail

WHEEL=${1:?usage: $0 <agentminder wheel>}
HERE=$(cd "$(dirname "$0")" && pwd)
SHARED=$HERE/shared

for app in incident-response-agent lb-diagnostic-agent k8s-diagnostic-agent vcf-diagnostic-agent; do
  dest=$HERE/$app
  cp "$SHARED/trust/pais-root.pem" "$SHARED/trust/model_proxy.py" "$dest/"
  cp "$SHARED/trust/profile" "$dest/.profile"
  for skill in "$dest"/.agents/skills/*/; do
    cp "$SHARED/findings.schema.json" "$skill"
  done
done

for app in lb-diagnostic-agent k8s-diagnostic-agent vcf-diagnostic-agent; do
  side=$HERE/$app/sidecar
  mkdir -p "$side/site-packages"
  cp "$SHARED/sidecar/run-sidecar.sh" "$SHARED/sidecar/mcp_bridge.py" "$SHARED/sidecar/agentminder-env.sh" "$side/"
  # A wheel is a zip of the installed package, so unpacking it is the install.
  if command -v unzip >/dev/null; then
    unzip -q -o "$WHEEL" -d "$side/site-packages"
  else
    python3 -m zipfile -e "$WHEEL" "$side/site-packages"
  fi
done

echo "staged the shared files and the SDK into the agent apps"
