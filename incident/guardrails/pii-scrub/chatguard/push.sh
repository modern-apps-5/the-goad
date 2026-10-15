#!/usr/bin/env bash
# Push the chat guard. Does not map it onto the incident chat.
# That map is a separate step after /ready returns origin ok.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PII="$(cd "${ROOT}/.." && pwd)"
CA="${TANZU_CA:-${HOME}/.config/tanzu-ca/opsman-root-ca.pem}"
if [[ ! -f "${CA}" ]]; then
  echo "missing platform CA at ${CA}" >&2
  exit 1
fi
cp "${PII}/scrub.py" "${PII}/guardrail.py" "${ROOT}/"
cp "${CA}" "${ROOT}/ca.pem"
cleanup() { rm -f "${ROOT}/scrub.py" "${ROOT}/guardrail.py" "${ROOT}/ca.pem"; }
trap cleanup EXIT
export PATH="${HOME}/.local/bin:${PATH}"
env -u CF_HOME cf target -o Goad -s "${GOAD_VCFA_SPACE:?GOAD_VCFA_SPACE is blank. See ASSEMBLE.md Step 0.}"
env -u CF_HOME cf push -f "${ROOT}/manifest.yml"
echo "pushed pii-chat-guard"
echo "health: https://pii-chat-guard.${TANZU_APPS_DOMAIN}/health"
