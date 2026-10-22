# Blanks

Values to fill at apply time. Do not commit real addresses, tokens, or
passwords. Examples are shapes. The users and catalog addresses are
written by the Job in `gitops/music-store-dev/users-vm/shop-endpoints.yaml`.
No address is in git.

| Blank | What it is | Example |
|---|---|---|
| `STORE_HOST` | Avi DNS name for the shop ingress | `store.example.lab` |
| `ZAMMAD_HOST` | Avi DNS name for Zammad | `zammad.example.lab` |
| `GRAFANA_HOST` | Avi DNS name for Grafana | `grafana.example.lab` |
| `POSTGRES_HOST` | DSM catalog address. The Job in `gitops/music-store-dev/users-vm` writes it | `203.0.113.10` |
| `USERS_HOST` | VM Service `users-service` address | `203.0.113.11` |
| `QWEN_BASE_URL` | Private AI OpenAI base, model id `qwen` | `https://203.0.113.12/api/v1/compatibility/openai/v1` |
| `QWEN_API_KEY` | Private AI API token. Not committed | (secret store) |
| `ZAMMAD_URL` | Zammad base URL | `https://zammad.example.lab` |
| `ZAMMAD_TOKEN` | Zammad API token. Not committed | (secret store) |
| `ZAMMAD_DB_PASSWORD` | Zammad Postgres password. Not committed | (secret store) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password. Not committed | (secret store) |
| `CLM_URL` | Orchestrator decision gate. POST `{CLM_URL}/v1/systemone`. Blank means the walk uses the fallback and the report says so | (blank until a CLM image exists) |
| `CLM_BASE_URL` | Same root, read by `agents/orchestrator/clm.py`. The pod env is `CLM_URL` | `http://clm.example.lab:8700` |
| `CLM_IMAGE` | Image for the CLM server. Empty means do not apply `clm/clm.yaml` | (empty until the image exists here) |
| `TANZU_APPS_DOMAIN` | Cloud Foundry apps domain for org `Goad` | `apps.example.lab` |
| `GOAD_VCFA_SPACE` | Tanzu space. The approved name is `metal-music-app-agentic-system` | `metal-music-app-agentic-system` |
| `INCIDENT_HOST` | Avi DNS name for a VKS chat ingress. The Tanzu chat route is `incident-response-agent.${TANZU_APPS_DOMAIN}` | `incident.example.lab` |
| `STORE_WORKER_VMS` | Comma-separated worker VM names the VCF agent passes to `vcf_vm_disk_latency` | `worker-a,worker-b` |
| `AGENTMINDER_HOST` | AgentMinder host already in this organization | `agentminder.example.lab` |
| `K8S_MCP_HOST` | Avi DNS name for the Kubernetes MCP | `k8s-mcp.example.lab` |
| `AVI_MCP_HOST` | Avi DNS name for the Avi MCP | `avi-mcp.example.lab` |
| `VCF_MCP_HOST` | Avi DNS name for the VCF MCP | `vcf-mcp.example.lab` |
| `IDSP_GATEWAY_K8S` | AgentMinder gateway route for the Kubernetes door. Empty until the client exists | (set by `agentminder/register.py`) |
| `IDSP_GATEWAY_AVI` | AgentMinder gateway route for the Avi door | (set by `agentminder/register.py`) |
| `IDSP_GATEWAY_VCF` | AgentMinder gateway route for the VCF door | (set by `agentminder/register.py`) |
| `VCF_MCP_AUDIENCES` | Comma-separated JWT audiences for the VCF door | (set by `agentminder/register.py`) |
| `KUBECONFIG` | Guest cluster kubeconfig. Not committed | (operator file) |

The shop database secret `store-db` and the chat secret
`metal-oracle-model` already live in namespace `music-store`. This
apply does not write them. The shop is `gitops/music-store-dev/app`.
Agent apply creates
`agent-doors`, `qwen-model`, `zammad-api`, `walk-targets`, and
`grafana-annotator` in `metal-music-app-agentic-system`. The key names
for every Secret apply creates are in `secrets/templates.yaml`. That
file is a blank template. It is not applied.

`CLM_URL` empty is the safe path. The orchestrator calls all three
diagnostic agents and the enrichment note says the decision gate is on
fallback.
