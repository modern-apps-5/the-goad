#!/usr/bin/env bash
# Check the lab before the agentic ops automation demo: main is at the
# start, the agentic ops engineer's Terraform plans no change, and the last
# push of the incident apps worked.
#
#   demos/agentic-ops-automation/check.sh
#
# It starts the workflow agentic-ops as a plan only, so it takes a few
# minutes. It changes nothing.
#
# Needs gh, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

SKILL=tanzu/metal-music-app-agentic-system/k8s-diagnostic-agent/.agents/skills/k8s_diagnostic_agent/SKILL.md
ok=true

if main_file terraform/agentic-ops/agentminder.tf | grep -q '"k8s_list_nodes"'; then
  ok=false
  echo "k8s_list_nodes is already registered in AgentMinder on main: run reset.sh."
fi
if main_file "$SKILL" | grep -q 'k8s_list_nodes'; then
  ok=false
  echo "The k8s diagnostic agent's skill already calls k8s_list_nodes on main: run reset.sh."
fi

gh run list -R "$REPO" -w tanzu-apps.yml -b main -L 1 --json conclusion,url \
  --jq '.[0] | "Last tanzu-apps run: \(.conclusion), \(.url)"' | tee "$DEMO_TMP/push"
grep -q 'run: success' "$DEMO_TMP/push" || { ok=false; echo "The last push of the incident apps did not succeed."; }
echo

echo "Planning terraform/agentic-ops, without apply."
run_workflow agentic-ops.yml -f apply=false
plan_summary "$RUN_ID" || { ok=false; echo "The plan has changes. Find out whose they are before the demo."; }

echo
$ok && echo "Ready for the demo." || { echo "Not ready."; exit 1; }
