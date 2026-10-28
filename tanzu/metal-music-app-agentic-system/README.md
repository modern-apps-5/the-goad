# Metal Music incident apps

The nine Cloud Foundry apps of the incident demo, in Tanzu Platform org
`Goad`, space `metal-music-app-agentic-system`, foundation `goad`. Each
directory is one app, pushed as it is. `manifest.yml` lists them all.

[.github/workflows/tanzu-apps.yml](../../.github/workflows/tanzu-apps.yml)
pushes them on every change to this directory on `main`, and from the
Actions page. Nobody pushes by hand. A first job installs the cf CLI and
its plugins once and passes them on, because that install takes minutes on
the runner. Then the workflow runs one job per app, so each push has its
own log. Each job:

1. installs the cf CLI from the foundation and logs in as `goad-deployer`
   ([.github/actions/cf-login](../../.github/actions/cf-login/action.yml));
2. pulls the AgentMinder SDK wheel from the private package
   `ghcr.io/modern-apps-5/agentminder-sdk`;
3. runs `stage.sh`, which copies `shared/` into the agents;
4. runs `cf push <app> -f manifest.yml` with the secrets in a vars file.

A last job adds the network policies the agents need on `apps.internal`,
once every push has succeeded.

The space and the user-provided services `goad-qwen` and `sc-*` are the
platform engineer's: [terraform/platform-engineer/tanzu.tf](../../terraform/platform-engineer/tanzu.tf).
The `am-*` services are the cloud admin's, below.

| App | What it is |
|---|---|
| `incident-response-agent` | The chat. Tanzu Agent Builder (`agent_buildpack`), `AGENTS.md` and one skill. Its one tool is the orchestrator |
| `metal-incident-live` | The orchestrator. Calls the three diagnostic agents, Qwen and Grafana. Exposes `enrich_latest_incident` and `enrich_status` on `POST /mcp` |
| `lb-diagnostic-agent`, `k8s-diagnostic-agent`, `vcf-diagnostic-agent` | Agent Builder agents. Each calls one MCP server through the AgentMinder sidecar |
| `metal-avi-mcp`, `metal-k8s-mcp`, `metal-vcf-mcp` | The MCP servers for Avi, the music store cluster, and VCF |
| `pii-scrub` | Removes personal data from text |

`shared/` holds what several agents use, kept once:

- `trust/`: the Goad model ingress CA, the local model proxy on
  `127.0.0.1:8765`, and the `.profile` that starts it. The ingress
  certificate is signed by its own CA and named for another host.
- `sidecar/`: AgentMinder Sidecar Mode. `agentminder-env.sh` finds the bound
  service tagged `agentminder-client` in `VCAP_SERVICES` and exports the
  client ID, secret and gateway URL the SDK reads. `run-sidecar.sh` and
  `trust/profile` source it, and `stage.sh` copies it into each agent's
  `sidecar/`. `run-sidecar.sh` serves
  `mcp_bridge.py` on `127.0.0.1:8181`, which wraps the SDK's
  `agentminder.sidecar` app: the SDK gets each agent's token and sends
  every tool call through the AgentMinder gateway. The test runs where the
  SDK is unpacked.
- `findings.schema.json`: the diagnostic agents' finding format.

## Secrets

`((name))` in `manifest.yml` is a value that is not in git. Most are GitHub
secrets, which the workflow writes to a vars file for the push and then
deletes:

| Manifest variable | GitHub secret |
|---|---|
| `qwen_api_key` | `INCIDENT_QWEN_API_KEY` |
| `k8s_token` | `INCIDENT_K8S_TOKEN` |
| `sidecar_token` | `INCIDENT_SIDECAR_TOKEN` |
| `zammad_token` | `INCIDENT_ZAMMAD_TOKEN` |
| `grafana_admin_password` | `INCIDENT_GRAFANA_ADMIN_PASSWORD` |
| `avi_username`, `avi_password` | `INCIDENT_AVI_USERNAME`, `INCIDENT_AVI_PASSWORD` |
| `mcp_read_token`, `mcp_write_token` | `INCIDENT_MCP_READ_TOKEN`, `INCIDENT_MCP_WRITE_TOKEN` |

The Qwen key, the K8s token and the sidecar token are also in the
user-provided services, so the platform engineer workflow reads the same
three secrets. Change one in both places at once: rerun the platform
engineer workflow, then this one.

The AgentMinder client ID, client secret and gateway URL are not in the
vars file or in GitHub. The cloud admin's Terraform
([terraform/cloud-admin/agentminder-registration](../../terraform/cloud-admin/agentminder-registration))
makes one user-provided service for each diagnostic agent: `am-lb-diagnostic-agent`,
`am-k8s-diagnostic-agent` and `am-vcf-diagnostic-agent`. Each is tagged
`agentminder-client`, and the manifest binds it to its agent. Run the
`cloud-admin` workflow with apply before this one, so the services exist: the push
fails without them. A changed client secret reaches an app on
`cf restart <app>`. The GitHub secrets `INCIDENT_AM_*_CLIENT_SECRET` that
held the clients before were deleted on 2026-10-28.

## Upgrading AgentMinder

Mirror the matching SDK with `scripts/mirror-agentminder-sdk.sh`, then
change `SDK_TAG` in the workflow.

## Starting a walk

`walk/demo.sh start` (in `incident-demo/`) slows the catalog and opens one
Zammad ticket. It does not start the agents. Type this in the chat on
`https://incident-response-agent.apps.goad.gpu.set.lab/`:

`pick up the latest incident ticket and enrich it`
