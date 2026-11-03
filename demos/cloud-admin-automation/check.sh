#!/usr/bin/env bash
# Check the lab before the cloud admin automation demo: the cloud admin's
# Terraform plans no change, and the org's memory reservation on main is at
# its start.
#
#   demos/cloud-admin-automation/check.sh
#
# It starts the workflow cloud-admin as a plan only, so it takes a few
# minutes. It changes nothing.
#
# Needs gh, jq and perl. Prints no secret.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
. "$here/../lib/github.sh"

START=32768
ok=true

reservation=$(main_file terraform/cloud-admin/org/lab.auto.tfvars |
  perl -0ne 'print $1 if /"west-1" = \{.*?memory_reservation_mib\s*=\s*(\d+)/s')
echo "On main: zone west-1 memory_reservation_mib $reservation"
[[ $reservation == "$START" ]] || { ok=false; echo "main is not at the start ($START): run reset.sh."; }
echo

echo "Planning the cloud admin's roots, without apply."
run_workflow cloud-admin.yml -f apply=false
plan_summary "$RUN_ID" || { ok=false; echo "The plan has changes. Find out whose they are before the demo."; }

echo
$ok && echo "Ready for the demo." || { echo "Not ready."; exit 1; }
