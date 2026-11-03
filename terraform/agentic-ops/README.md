# Agentic ops engineer: AgentMinder registration

The agentic ops engineer's Terraform root. It registers the incident demo's
agents and MCP servers in the AgentMinder that
[../cloud-admin/agentminder](../cloud-admin/agentminder) installed, and
wires the agents' `am-*` and `sc-*` services. Apply the cloud admin's roots
and `terraform/platform-engineer` first: AgentMinder and the space must
exist. The state is `goad-agentic-ops`. See
[decisions 41 and 50](../../docs/decisions.md).

It is a separate root because the `restapi` provider's configuration needs
AgentMinder running. One root could not plan a fresh build.

| File | What it creates |
|---|---|
| `providers.tf` | Takes the admin client from two variables, gets a token from AgentMinder, and configures the `restapi` providers with it. |
| `agentminder.tf` | The MCP resource servers, the clients, one role policy for each diagnostic client, and each client's entry in `AuthClientPolicy`. |
| `cloudfoundry.tf` | One `am-*` user-provided service for each diagnostic agent, in org `Goad`, space `metal-music-app-agentic-system`. |
| `tools.tf` | The `sc-*` user-provided services: the orchestrator's tool and one for each diagnostic agent's sidecar. |
| `outputs.tf` | `agent_clients` and `mcp_servers`, for people. |

## What it creates

- Three MCP resource servers, `goad-avi-mcp`, `goad-k8s-mcp`, and
  `goad-vcf-mcp`. Each points at
  `https://metal-<name>-mcp.apps.goad.gpu.set.lab/mcp`. Its primary
  audience is its route on the AgentMinder gateway.
- Four clients: `py-goad-lb`, `py-goad-k8s`, `py-goad-vcf`, and
  `py-goad-incident-response`. The incident response agent has no MCP
  server.
- One role policy for each diagnostic client. It allows the tools of that
  client's own server.
- Each client, added to AgentMinder's `AuthClientPolicy`.
- Three user-provided services, `am-lb-diagnostic-agent`,
  `am-k8s-diagnostic-agent`, and `am-vcf-diagnostic-agent`. Each is tagged
  `agentminder-client` and holds `client_id`, `client_secret`, and
  `gateway_url`. The space is the platform engineer's: this root only
  reads it.
- Four `sc-*` user-provided services, tagged `mcp-server`:
  `sc-incident-response-agent-orch`, which points at the orchestrator, and
  `sc-lb-diagnostic-agent-avi`, `sc-k8s-diagnostic-agent-k8s` and
  `sc-vcf-diagnostic-agent-vcf`, which point at each agent's sidecar and
  hold `incident_sidecar_token`. They were the platform engineer's, in
  `tanzu.tf`. This root imports them with `import` blocks, and the
  platform engineer's root has a `removed` block for each with
  `destroy = false`. Either root can apply first and nothing is deleted.
  Remove the blocks once they are in every state.

## Login

The root logs in to AgentMinder as the default tenant's admin OAuth client.
The `ssp` chart makes that client on its first install and keeps it in the
Secret `ssp-ssp-secret-defaulttenantclient`, in the namespace `ssp` of the
AgentMinder cluster. The root reads no cluster and no remote state. It takes
the client as two sensitive variables, `agentminder_client_id` and
`agentminder_client_secret`. The GitHub secrets are
`AGENTIC_OPS_AGENTMINDER_CLIENT_ID` and
`AGENTIC_OPS_AGENTMINDER_CLIENT_SECRET`.

The cloud admin copies the two values once, without printing them. The
commands are in [../runner/README.md](../runner/README.md). The client has
full admin in AgentMinder, so the agentic ops engineer does too. AgentMinder
has no service accounts yet. When it has, use one here.

The Cloud Foundry login is an access token, `CF_ACCESS_TOKEN`, that the
`cf-token` action gets as `goad-deployer`.

The provider is `restapi`, not `terracurl`. Terraform gets a new token on
every run, restapi reads each object back, and it can import. See decision 41.

The token comes from an `http` data source, not from restapi's
`oauth_client_credentials`. In restapi 3.0.0 the token request ignores
`insecure` and fails on the chart's self-signed certificate.

## Run it

The root reads no remote state, so it needs no `TF_HTTP_PASSWORD`.
`backend.hcl` is still needed for the state itself.

```sh
cp terraform.tfvars.example terraform.tfvars   # the admin client and the sidecar token; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
export CF_ACCESS_TOKEN=$(~/.claude/skills/lab-creds/cf-token.py)
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan >/dev/null
terraform show -json tfplan | jq -r '
  [.resource_changes[] | select(.change.actions != ["no-op"])
   | "\(.change.actions | join(",")) \(.address)"] | .[]'
terraform apply tfplan >/dev/null
```

The other lab values are in `lab.auto.tfvars`.

Do not print the plan or paste it anywhere. AgentMinder returns each
client's secret when it reads the client. `restapi` keeps the response in
attributes that are not marked sensitive, so a plan can show the old
secret. Use the commands above, as the workflow does. Do the same for
`apply`.

## In GitHub

Actions, `agentic-ops`, **Run workflow**. Tick `apply` to apply. It applies
only on `main`. The job's summary lists each resource and its action, and
nothing else. It runs the `cf-token` action, and uses the repository
secrets `AGENTIC_OPS_AGENTMINDER_CLIENT_ID`,
`AGENTIC_OPS_AGENTMINDER_CLIENT_SECRET`, `INCIDENT_SIDECAR_TOKEN`,
`TANZU_HUB_CLIENT_ASSERTION` and `GITEA_STATE_TOKEN`.

## Outputs

| Output | Holds |
|---|---|
| `agent_clients` | The client ID and gateway URL of each diagnostic agent, keyed `lb`, `k8s`, and `vcf` |
| `mcp_servers` | The app ID and gateway URL of each MCP server |

The outputs are for people. The apps do not read them. They get the client
ID, secret, and gateway URL from the `am-*` services, which the manifest in
[../../../tanzu/metal-music-app-agentic-system](../../../tanzu/metal-music-app-agentic-system)
binds. `shared/sidecar/agentminder-env.sh` turns the bound service into the
variables the SDK reads. A changed client secret reaches an app on
`cf restart <app>`. `tanzu-apps.yml` has no AgentMinder values and reads no
state.

The secrets go from AgentMinder to Terraform to Cloud Foundry, never through
GitHub. Terraform writing GitHub secrets would need a PAT or GitHub App key
that can write repository secrets (`GITHUB_TOKEN` cannot), and `tanzu-apps`
would still carry the values. See decision 41.

Anyone with the Gitea state token can read the client secrets in this
root's state, and anyone who can read the `am-*` services can read them
there. Secret Store is a later step.

## The move from cloud-admin

This root was `terraform/cloud-admin/agentminder-registration`, with the state
`goad-cloud-admin-agentminder-registration`. Resource addresses did not
change. Move the state once, by hand, before the merge. Initialize the
old state, with the old address in `backend.tf`. Then change the address,
lock address and unlock address to `goad-agentic-ops` and run
`terraform init -migrate-state -backend-config=backend.hcl`. The first plan must show no changes except
the `sc-*` imports. Keep the old state in Gitea until that plan is clean,
then delete it.

## The one-time import

`incident-demo/agentminder/register.py` made these objects first. The
first apply, on 2026-10-28, adopted them with `import` blocks, so the agents
kept their client IDs and secrets. Those blocks are gone: on a new
AgentMinder the first apply creates every object.
