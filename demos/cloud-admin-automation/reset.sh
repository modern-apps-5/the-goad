#!/usr/bin/env bash
# Put the lab back after the cloud admin automation demo: the org's memory
# reservation in zone west-1 back to 32768 MiB, the same way the demo
# changed it.
#
#   demos/cloud-admin-automation/reset.sh
#
# It opens a pull request with the value, merges it to main, and runs the
# workflow cloud-admin with apply. If main is already at the start, it
# only runs the workflow, so the lab matches main.
#
# Needs gh, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

START=32768

branch=demo-cloud-admin-reset-$(date +%Y%m%d%H%M%S)
new_branch "$branch"
if edit_file "$branch" terraform/cloud-admin/org/lab.auto.tfvars \
  "s/(\"west-1\" = \\{.*?memory_reservation_mib\\s*=\\s*)\\d+/\${1}$START/s" \
  "Put the org's memory reservation back to $START MiB"; then
  merge_branch "$branch" "Cloud admin demo: put the lab back" \
    "After the cloud admin automation demo: memory_reservation_mib $START in zone west-1. Opened by demos/cloud-admin-automation/reset.sh."
else
  [[ $? == 3 ]] || exit 1
  delete_branch "$branch"
  echo "main is already at the start."
fi

echo "Applying the cloud admin's roots."
run_workflow cloud-admin.yml -f apply=true
plan_summary "$RUN_ID" || true
echo "The lab is back at the start."
