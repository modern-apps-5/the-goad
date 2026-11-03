# Source this, do not run it. Exports the agent's AgentMinder client, from
# the one bound user-provided service tagged agentminder-client, as the
# variables the AgentMinder SDK and sidecar read. The agentic ops
# engineer's Terraform (terraform/agentic-ops) makes those services.
#
# run-sidecar.sh sources it for the sidecar, and .profile for the web
# process. Cloud Foundry gives a bound service's credentials only in
# VCAP_SERVICES, and the SDK reads plain variables. Prints no value.
#
# The client is used both as the sidecar's agent and as its orchestrator.
# The gateway URL is both the resource URL and its audience.
_am_env=$(python3 - <<'PY'
import json, os, shlex, sys

services = json.loads(os.environ.get("VCAP_SERVICES") or "{}")
bound = [s for group in services.values() for s in group
         if "agentminder-client" in (s.get("tags") or [])]
if len(bound) != 1:
    print(f"agentminder-env: {len(bound)} services tagged agentminder-client, need 1", file=sys.stderr)
    sys.exit(1)
creds = bound[0]["credentials"]
values = {
    "AM_CLIENT_ID": creds["client_id"],
    "AM_CLIENT_SECRET": creds["client_secret"],
    "AM_GATEWAY": creds["gateway_url"],
    "AGENTMINDER_SIDECAR_AGENT_CLIENT_ID": creds["client_id"],
    "AGENTMINDER_SIDECAR_AGENT_CLIENT_SECRET": creds["client_secret"],
    "AGENTMINDER_ORCHESTRATOR_CLIENT_ID": creds["client_id"],
    "AGENTMINDER_ORCHESTRATOR_CLIENT_SECRET": creds["client_secret"],
    "AGENTMINDER_SIDECAR_RESOURCE_0_URL": creds["gateway_url"],
    "AGENTMINDER_SIDECAR_RESOURCE_0_AUDIENCE": creds["gateway_url"],
}
for name, value in values.items():
    print(f"export {name}={shlex.quote(value)}")
print(f"agentminder-env: client from {bound[0]['name']}", file=sys.stderr)
PY
)
_am_status=$?
[ "$_am_status" -eq 0 ] && eval "$_am_env"
unset _am_env
# The last status is the script's, for "source ... || ...".
[ "$_am_status" -eq 0 ] && unset _am_status || { unset _am_status; false; }
