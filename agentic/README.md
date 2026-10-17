# Agentic demo

Reusable manifests for the Metal Music Store incident demo. They run in
the same organization as the shop. Nothing here is a secret, and nothing
here names a second organization.

The Red Lab store is `gitops/music-store`: the users VM Service VM, the
DSM catalog, and the VKS cluster. This directory does not copy that
tree. `store/` only publishes the guest Service names and the shop
ingress. Do not apply `app/music-store`. Those container files are the
earlier shape.

## Where each piece runs

| Piece | Cluster | Namespace |
|---|---|---|
| Shop ingress and backing Service names | `music-store` | `metal-music-store` |
| Users VM, DSM catalog, VKS cluster | supervisor | `gitops/music-store` |
| Four agents, three MCP servers, pii-scrub | `music-store` | `metal-music-app-agentic-system` |
| Zammad and Grafana | `music-store` | `incident-tools` |
| Qwen | Private AI `ModelEndpoint` `qwen` | the Private AI namespace |
| CLM | inside this organization, not a GPU box outside it | see `clm/README.md` |

`demo/demo.sh start` slows catalog queries and opens one Zammad ticket.
It does not start the agents.

Fill `BLANKS.md` before apply. `apply.py` reads the environment and
refuses to run while a required name is empty.
