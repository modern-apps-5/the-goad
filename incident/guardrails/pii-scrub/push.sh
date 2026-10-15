#!/usr/bin/env bash
# Push the AI Services Presidio webhook. Never prints tokens.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"
cf target -o Goad -s "${GOAD_VCFA_SPACE:?GOAD_VCFA_SPACE is blank. See ASSEMBLE.md Step 0.}"
cf push -f "${ROOT}/manifest.yml"
echo "pushed pii-scrub"
echo "health: https://pii-scrub.${TANZU_APPS_DOMAIN}/health"
