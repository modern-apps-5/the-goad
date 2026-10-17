# Agentic demo

Reusable manifests for the Metal Music Store incident demo. They run in
the same organization as the shop. Nothing here is a secret, and nothing
here names a second organization.

`gitops/music-store` is the users VM, the DSM catalog, and the VKS
cluster. `store/` is the storefront that was copied from the other
org: store, cart, orders, and chat, plus the ingress and the Service
names `users-service` and `postgres-service`. Do not apply
`app/music-store`. Those container files are the earlier shape.

The incident response agent, the orchestrator, and the three diagnostic
agents are in `agents/`. Skills are `agents/<name>/skills/SKILL.md`.
`CLM_URL` blank in `BLANKS.md` means the decision gate runs on fallback
and the report says so. `demo/demo.sh start` only slows the store and
opens the Zammad ticket. It does not start the agents. Secret shapes
are in `secrets/templates.yaml`. `apply.py` fills them. That file is
not applied as-is.

## Where each piece runs

| Piece | Cluster | Namespace |
|---|---|---|
| Storefront, cart, orders, chat, ingress | `music-store` | `metal-music-store` |
| Users VM, DSM catalog, VKS cluster | supervisor | `gitops/music-store` |
| Incident response chat, orchestrator, three diagnostic agents, three MCP servers, pii-scrub | `music-store` | `metal-music-app-agentic-system` |
| Zammad and Grafana | `music-store` | `incident-tools` |
| Qwen | Private AI `ModelEndpoint` `qwen` | the Private AI namespace |
| CLM | inside this organization, not a GPU box outside it | see `clm/README.md` |

`demo/demo.sh start` slows catalog queries and opens one Zammad ticket.
It does not start the agents.

Fill `BLANKS.md` before apply. `apply.py` reads the environment and
refuses to run while a required name is empty.
