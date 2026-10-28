# Cloud admin, stage 4: AgentMinder registration

The cloud admin's fourth Terraform root. It registers the incident demo's
agents and MCP servers in the AgentMinder that
[../agentminder](../agentminder) installed. Apply `terraform/cloud-admin/org`,
`org-config`, and `agentminder` first. The state is
`goad-cloud-admin-agentminder-registration`. See
[decision 41](../../../docs/decisions.md).

It is a separate root because the `restapi` provider's configuration needs
AgentMinder running, and stage 3 creates it. One root could not plan a
fresh build.

| File | What it creates |
|---|---|
| `providers.tf` | Logs in to VCF Automation, gets the AgentMinder cluster's kubeconfig, reads the admin client from the cluster, and configures the `restapi` provider with it. |
| `agentminder.tf` | The MCP resource servers, the clients, one role policy for each diagnostic client, and each client's entry in `AuthClientPolicy`. |
| `cloudfoundry.tf` | One user-provided service for each diagnostic agent, in org `Goad`, space `metal-music-app-agentic-system`. |
| `outputs.tf` | `agent_clients` and `mcp_servers`, for people. |
| `imports.tf` | One time only: adopts the objects `register.py` made. |

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

## Login

The root logs in to VCF Automation as `cloud-admin`, with
`cloud_admin_password`, as stage 3 does. It reads the state of
[../org-config](../org-config) for the cluster names, and gets the
AgentMinder cluster's kubeconfig with `vcfa_vks_cluster_kubeconfig`.

Then a `kubernetes_secret_v1` data source reads the `ssp` chart's Secret
`ssp-ssp-secret-defaulttenantclient`, in the namespace `ssp`. That is the
default tenant's admin OAuth client, and it configures the `restapi`
provider. Stage 3 has no outputs for it and passes no secret through
remote state.

AgentMinder has no service accounts yet. When it has, use one here.

The Cloud Foundry login is an access token, `CF_ACCESS_TOKEN`, that the
`cf-token` action gets as `goad-deployer`.

The provider is `restapi`, not `terracurl`. Terraform gets a new token on
every run, restapi reads each object back, and it can import. See decision 41.

The token comes from an `http` data source, not from restapi's
`oauth_client_credentials`. In restapi 3.0.0 the token request ignores
`insecure` and fails on the chart's self-signed certificate.

## Run it

The remote state of `org-config` is read with the `http` backend. A data
source cannot read `backend.hcl`, so the token must also be in the
environment, with the Cloud Foundry token.

```sh
cp terraform.tfvars.example terraform.tfvars   # cloud_admin_password; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
export TF_HTTP_PASSWORD=<the same token>
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

Actions, `cloud-admin`, **Run workflow**. This root is its fourth job,
`agentminder-registration`, after `agentminder`. Tick `apply` to apply. It
applies only on `main`. The job's summary lists each resource and its
action, and nothing else. It runs the `cf-token` action, and uses the
repository secrets `CLOUD_ADMIN_PASSWORD` and `GITEA_STATE_TOKEN`.

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

## The one-time import

`incident-demo/agentminder/register.py` made these objects first, and
the running agents use their IDs and secrets. `imports.tf` finds each
object by name and adopts it, so the first apply changes nothing for the
agents. The grants in `AuthClientPolicy` are not imported: the first apply
adds each client again.

Delete `imports.tf` after the first apply. On a new AgentMinder its
lookups find nothing and fail the plan.

## Rollout order

1. Merge the branch. The `tanzu-apps` run on merge fails until the `am-*`
   services exist. Running apps are not affected.
2. Run `cloud-admin.yml` with `apply`. The earlier jobs should show no
   changes. The new job imports the `register.py` objects and makes the
   `am-*` services.
3. Run `tanzu-apps.yml` again.
4. Delete `imports.tf` in a follow-up pull request.
5. Delete the GitHub secrets `INCIDENT_AM_LB_CLIENT_SECRET`,
   `INCIDENT_AM_K8S_CLIENT_SECRET`, and `INCIDENT_AM_VCF_CLIENT_SECRET`.
