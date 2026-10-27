# Incident demo

The Metal Music incident demo. It runs beside the shop. Nothing here is
a secret. The shop is not in this tree. Argo CD syncs it from
`gitops/music-store-dev/app` into namespace `music-store`.

| Directory | What it is |
|---|---|
| `observability/` | Prometheus, Grafana, the architecture board, the topology panel, and the probe |
| `zammad/` | Zammad |
| `agents/` | The four agents, their skills, and `agents/orchestrator/` |
| `tanzu-agents/` | Cloud Foundry manifests and `push.py` |
| `mcp/` | Kubernetes, Avi, and VCF doors |
| `pii/` | `scrub.py` |
| `clm/` | Decision gate. Empty `CLM_IMAGE` means apply skips it |
| `agentminder/` | Client registration |
| `walk/` | `walk/demo.sh start` slows the catalog and opens one ticket. It does not start the agents |
| `secrets/templates.yaml` | Secret shapes. Not applied as a manifest |

`apply.py` fills observability, Zammad, the agents, and the MCP servers.
`tanzu-agents/push.py` fills the Cloud Foundry apps. Neither file is
applied by Argo CD. Fill `BLANKS.md` first. Lessons and the rebuild
order are in `RUNBOOK.md`. The shop, and the order it is deployed in,
are in [gitops/README.md](../gitops/README.md). This tree is at the
repository root because a person runs it; `gitops/` holds only what
Argo CD syncs.

## Where each piece runs

| Piece | Cluster | Namespace |
|---|---|---|
| Storefront, cart, orders, chat, ingress | `music-store` | `music-store` |
| Users VM, DSM catalog, VKS cluster | supervisor | `music-store` Supervisor Namespace, from `gitops/music-store` and `gitops/music-store-dev/users-vm` |
| Incident response chat, orchestrator, three diagnostic agents, three MCP servers, pii-scrub | Tanzu Platform org `Goad` | space `metal-music-app-agentic-system` |
| Zammad and Grafana | `music-store` | `incident-tools` |
| Qwen | Private AI `ModelEndpoint` `qwen` | the Private AI namespace |
| CLM | inside this organization | see `clm/README.md` |
