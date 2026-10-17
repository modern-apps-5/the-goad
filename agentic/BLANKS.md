# Blanks

Values to fill at apply time. Do not commit real addresses, tokens, or
passwords. Examples are shapes.

| Blank | What it is | Example |
|---|---|---|
| `STORE_HOST` | Avi DNS name for the shop ingress | `store.example.lab` |
| `ZAMMAD_HOST` | Avi DNS name for Zammad | `zammad.example.lab` |
| `GRAFANA_HOST` | Avi DNS name for Grafana | `grafana.example.lab` |
| `POSTGRES_HOST` | DSM catalog address, from the live `PostgresCluster` status | `203.0.113.10` |
| `USERS_HOST` | VM Service `users-service` address | `203.0.113.11` |
| `QWEN_BASE_URL` | Private AI OpenAI base, model id `qwen` | `https://203.0.113.12/api/v1/compatibility/openai/v1` |
| `QWEN_API_KEY` | Private AI API token. Not committed | (secret store) |
| `ZAMMAD_URL` | Zammad base URL | `https://zammad.example.lab` |
| `ZAMMAD_TOKEN` | Zammad API token. Not committed | (secret store) |
| `ZAMMAD_DB_PASSWORD` | Zammad Postgres password. Not committed | (secret store) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password. Not committed | (secret store) |
| `CLM_BASE_URL` | CLM root inside this organization. POST `/v1/systemone`, model `clm-latest`, no key | `http://clm.example.lab:8700` |
| `CLM_IMAGE` | Image for the CLM server. Empty means do not apply `clm/clm.yaml` | (empty until the image exists here) |
| `AGENTMINDER_HOST` | AgentMinder host already in this organization | `agentminder.example.lab` |
| `K8S_MCP_HOST` | Avi DNS name for the Kubernetes MCP | `k8s-mcp.example.lab` |
| `AVI_MCP_HOST` | Avi DNS name for the Avi MCP | `avi-mcp.example.lab` |
| `VCF_MCP_HOST` | Avi DNS name for the VCF MCP | `vcf-mcp.example.lab` |
| `IDSP_GATEWAY_K8S` | AgentMinder gateway route for the Kubernetes door. Empty until the client exists | (set by `agentminder/register.py`) |
| `IDSP_GATEWAY_AVI` | AgentMinder gateway route for the Avi door | (set by `agentminder/register.py`) |
| `IDSP_GATEWAY_VCF` | AgentMinder gateway route for the VCF door | (set by `agentminder/register.py`) |
| `VCF_MCP_AUDIENCES` | Comma-separated JWT audiences for the VCF door | (set by `agentminder/register.py`) |
| `KUBECONFIG` | Guest cluster kubeconfig. Not committed | (operator file) |

The shop database user and password stay the ones already published in
`app/music-store`. This directory does not add another copy.
