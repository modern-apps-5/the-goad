# Agentic demo

Reusable manifests for the Metal Music Store incident demo. They run in
the same organization as the shop. Nothing here is a secret, and nothing
here names a second organization.

The shop containers stay in `app/music-store`. This directory only adds
the overlay that selects which of those files to run, plus the agentic
pieces. Do not apply `k8s-users-deployment.yaml` or
`k8s-database-deployment.yaml`. Users are the VM Service VM in
`gitops/music-store/users-vm.yaml`. The catalog is the DSM
`PostgresCluster` in `gitops/music-store/catalog.yaml`.

## Where each piece runs

| Piece | Cluster | Namespace |
|---|---|---|
| Store, cart, orders, chat, traffic generator | `music-store` | `metal-music-store` |
| Four agents, three MCP servers, pii-scrub | `music-store` | `metal-music-app-agentic-system` |
| Zammad and Grafana | `music-store` | `incident-tools` |
| Qwen | Private AI `ModelEndpoint` `qwen` | the Private AI namespace |
| CLM | inside this organization, not a GPU box outside it | see `clm/README.md` |

`demo/demo.sh start` slows catalog queries and opens one Zammad ticket.
It does not start the agents.

Fill `BLANKS.md` before apply. `apply.py` reads the environment and
refuses to run while a required name is empty.
