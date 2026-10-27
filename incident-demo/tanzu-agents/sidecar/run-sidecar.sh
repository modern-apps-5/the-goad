#!/usr/bin/env bash
# Official AgentMinder Sidecar Mode.
# https://techdocs.broadcom.com/us/en/symantec-security-software/identity-security/agentminder/4-1/developer-resources/sidecar-mode.html
#
# Serves mcp_bridge:app, which delegates every MCP method to the official
# agentminder.sidecar:app and only answers the transport obligations that
# app skips (notification 202, GET 405, DELETE 204, unknown method -32601).
# If this nest's gateway returns 2002 on initialize, the bridge keeps the
# process up. tools/list is asked of the live VCF MCP. tools/call still
# goes through the official app. Grant and revoke stay enforced. Loopback only.
set -euo pipefail
if [[ -z "${AGENTMINDER_SIDECAR_TOKEN:-}" ]]; then
  echo "agentminder sidecar: AGENTMINDER_SIDECAR_TOKEN is required (product)" >&2
  exit 2
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
# Lab AgentMinder uses a private CA. Export TLS paths here, not as CF
# app env: python_buildpack reads SSL_CERT_FILE during pip staging and
# the droplet path does not exist yet.
if [[ -n "${AGENTMINDER_CA_BUNDLE:-}" && -f "${AGENTMINDER_CA_BUNDLE}" ]]; then
  export SSL_CERT_FILE="${AGENTMINDER_CA_BUNDLE}"
  export REQUESTS_CA_BUNDLE="${AGENTMINDER_CA_BUNDLE}"
fi
export PYTHONPATH="${HERE}${PYTHONPATH:+:${PYTHONPATH}}"
if [[ -d "${HERE}/site-packages" ]]; then
  export PYTHONPATH="${HERE}/site-packages:${PYTHONPATH}"
fi
if ! python3 -c "import agentminder.sidecar" >/dev/null 2>&1; then
  echo "agentminder sidecar: official package missing (pip install agentminder[sidecar] / extract SDK image)" >&2
  exit 2
fi
if ! python3 -c "import mcp_bridge" >/dev/null 2>&1; then
  echo "agentminder sidecar: mcp_bridge missing next to run-sidecar.sh" >&2
  exit 2
fi
exec python3 -m uvicorn mcp_bridge:app --host 127.0.0.1 --port 8181
