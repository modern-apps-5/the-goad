#!/usr/bin/env bash
# Put the lab back after the agentic ops automation demo: take the step
# that calls k8s_list_nodes out of the k8s diagnostic agent's skill, and
# take k8s_list_nodes out of AgentMinder, the same way the demo put them in.
#
#   demos/agentic-ops-automation/reset.sh
#
# It opens one pull request with both files and merges it to main. The
# merge starts the workflow tanzu-apps, which pushes the apps again; the
# script waits for it. Then it runs the workflow agentic-ops with apply.
# It does not make the catalog fast again: incident.sh stop does that.
#
# Needs gh, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

SKILL=tanzu/metal-music-app-agentic-system/k8s-diagnostic-agent/.agents/skills/k8s_diagnostic_agent/SKILL.md

branch=demo-agentic-ops-reset-$(date +%Y%m%d%H%M%S)
new_branch "$branch"
changed=()
edit_file "$branch" "$SKILL" \
  's/^\d+\. \*\*Nodes\.\*\*.*\n//m' \
  "Take the nodes step out of the k8s diagnostic agent's skill" &&
  changed+=(skill) || [[ $? == 3 ]]
edit_file "$branch" terraform/agentic-ops/agentminder.tf \
  's/^\s*"k8s_list_nodes",\n//m' \
  "Take k8s_list_nodes out of AgentMinder" &&
  changed+=(agentminder) || [[ $? == 3 ]]

if ((${#changed[@]} == 0)); then
  delete_branch "$branch"
  echo "main is already at the start."
else
  merge_branch "$branch" "Agentic ops demo: put the lab back" \
    "After the agentic ops automation demo: no k8s_list_nodes in the k8s diagnostic agent's skill or in AgentMinder. Opened by demos/agentic-ops-automation/reset.sh."
  if [[ " ${changed[*]} " == *" skill "* ]]; then
    echo "Waiting for tanzu-apps to push the agents again."
    wait_push_run tanzu-apps.yml "$MERGE_SHA"
  fi
fi

echo "Applying terraform/agentic-ops."
run_workflow agentic-ops.yml -f apply=true
plan_summary "$RUN_ID" || true
echo "The lab is back at the start."
