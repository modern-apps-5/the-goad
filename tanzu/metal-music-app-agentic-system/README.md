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

The space and the user-provided services `goad-qwen`, `k8s-mcp-cluster`
and `sc-*` are the platform engineer's: [terraform/platform-engineer/tanzu.tf](../../terraform/platform-engineer/tanzu.tf).
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

The K8s token is the token of the service account `goad-k8s-mcp` in
namespace `platform-tools` of the music store cluster, from the Secret
`goad-k8s-mcp-token` that `gitops/music-store-platform` makes. It does not
expire.

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

`scripts/incident-walk.sh start` slows the catalog and opens one Zammad
ticket. It does not start the agents. It runs `kubectl` against the music
store cluster's current context, and reads `STORE_URL`, `ZAMMAD_URL` and
`ZAMMAD_TOKEN` from the environment. Then type this in the chat on
`https://incident-response-agent.apps.goad.gpu.set.lab/`:

`pick up the latest incident ticket and enrich it`

A walk has passed when:

- the chat lists the ticket and each diagnostic step, and the line
  `Decision gate: CLM fallback (CLM_URL is unset)`;
- Grafana (`http://grafana.goad.gpu.set.lab`) has one annotation tagged
  `incident` for each step;
- the newest Zammad ticket has one article with the subject `Enrichment`
  whose body names storage latency as the root cause.

`/health` answering 200 on every app is not a passed walk. `avi_latency`
may be denied with HTTP 403: the account on the cluster can sign in to Avi
but not read virtual services. The note still posts.

## Lessons

- The foundation has one Diego cell, about 16 GB, and Diego places apps
  by reservation, not by memory used. `cf start` fails with
  `InsufficientResources` while the cell still has free memory. Shrink
  other apps' reservations before staging these nine. The Java app
  `autoscale-api` needs 1024M; with 512M it exits at once.
- `apps.internal` does not answer until the destination app has a route
  on it (`cf map-route APP apps.internal --hostname APP`). A network
  policy alone leaves bosh-dns with an empty answer, and the chat reports
  `URLError` in under a second. `metal-incident-live` and the three
  diagnostic agents have that route in the manifest.
- `cf add-network-policy` takes the destination app as a positional
  argument (`SOURCE DESTINATION`), not `--destination-app`.
- Qwen is the Private AI `ModelEndpoint` `qwen-14b-xlarge`. 1.5B weights
  are too small to call tools.
- AgentMinder's console is
  `https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/`. `/`
  is a Spring 404.
- The orchestrator's decision gate is CLM, a routing model that is not
  installed in this lab. With `CLM_URL` unset it calls all three
  diagnostic agents and says so in the note.
