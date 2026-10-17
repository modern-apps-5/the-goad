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
| `KUBECONFIG` | Guest cluster kubeconfig. Not committed | (operator file) |

The shop database user and password stay the ones already published in
`app/music-store`. This directory does not add another copy.
