#!/usr/bin/env bash
# Turn the virtual patch on the users VM on and off.
#
#   demos/vdefend-virtual-patching/patch.sh on       the rule resets matching traffic (DETECT_PREVENT)
#   demos/vdefend-virtual-patching/patch.sh off      the rule only logs it (DETECT), the baseline
#   demos/vdefend-virtual-patching/patch.sh status   the rule's action now, and the project's IDPS events
#
# It changes the action of the rule users-vm-inbound in the IDPS policy
# music-users, which terraform/security-admin/idps.tf creates in the goad
# org's NSX project. The change goes straight to NSX Manager, so it takes
# effect in seconds. It is drift from Terraform while it lasts: the next
# security-admin apply puts DETECT back. Run "off" after the demo.
#
# Needs curl and jq, and these in the environment:
#
#   NSX_HOST      NSX Manager, for example nsx01.gpu.set.lab
#   NSX_USER      an NSX user who may edit the goad project's IDPS policy
#   NSX_PASSWORD  that user's password. Never printed.
#   NSX_CACERT    optional: a PEM file that verifies NSX Manager's
#                 certificate, when the system's trust store does not
#   NSX_PROJECT   optional: the NSX project's display name, goad by default
set -euo pipefail

usage() { echo "usage: $0 on|off|status" >&2; exit 2; }
case ${1:-} in on | off | status) ;; *) usage ;; esac
: "${NSX_HOST:?set NSX_HOST}" "${NSX_USER:?set NSX_USER}" "${NSX_PASSWORD:?set NSX_PASSWORD}"
project_name=${NSX_PROJECT:-goad}

# The password goes to curl in a config on stdin, not on its command line.
nsx() {
  local path=$1; shift
  local tls=()
  [[ -n ${NSX_CACERT:-} ]] && tls=(--cacert "$NSX_CACERT")
  printf 'user = "%s:%s"\n' "$NSX_USER" "$NSX_PASSWORD" |
    curl -sS --fail-with-body "${tls[@]}" -K - -H 'Content-Type: application/json' \
      "https://$NSX_HOST/policy/api/v1$path" "$@"
}

project_id=$(nsx /orgs/default/projects |
  jq -r --arg name "$project_name" '.results[] | select(.display_name == $name) | .id')
[[ -n $project_id ]] || { echo "No NSX project named $project_name" >&2; exit 1; }
rule=/orgs/default/projects/$project_id/infra/domains/default/intrusion-service-policies/music-users/rules/users-vm-inbound

show() {
  nsx "$rule" | jq -r '"users-vm-inbound: \(.action)"'
}

# The project's IDPS events, one line per signature, as NSX Manager's
# Security > IDS/IPS & Malware Prevention > Events shows them.
events() {
  nsx "/orgs/default/projects/$project_id/infra/settings/firewall/security/intrusion-services/ids-events" \
    -X POST -d '{}' |
    jq -r '.results[] | "  \(.count)x  \(.severity)  \(.signature_id)  \(.signature_name)"'
}

case $1 in
  status) show; echo "IDPS events in project $project_name:"; events; exit 0 ;;
  on) action=DETECT_PREVENT ;;
  off) action=DETECT ;;
esac

# NSX resets the fields a rule PATCH leaves out, so send the whole rule
# back with only the action changed. curl reads its config from stdin, so
# the body goes through a file.
body=$(mktemp)
trap 'rm -f "$body"' EXIT
nsx "$rule" | jq -c --arg action "$action" '.action = $action' > "$body"
nsx "$rule" -X PATCH -d @"$body" >/dev/null
show
