# gitops

What Argo CD syncs, and the incident demo that sits beside it. A commit
on `main` is how `gitops/` changes. Terraform creates the Argo CD
Applications. Those Applications are not edited from this directory.

## Deploy order

1. Cloud admin Terraform: `terraform/cloud-admin/org`, then
   `terraform/cloud-admin/org-config`, then
   `terraform/cloud-admin/agentminder`.
2. Platform engineer Terraform: `terraform/platform-engineer`. That
   creates the Supervisor Namespaces, Argo CD, and the Applications
   that point at the directories below.
3. Argo CD, in this order. The platform applications do not wait on
   each other. The developer applications need the cluster and the
   catalog from `music-store`.
   - `private-ai` — wave 0 database, wave 1 the address Job, wave 2
     Private AI Services, wave 3 model `qwen-14b-xlarge`.
   - `music-store/` — one folder, three Applications. The parent
     Application `music-store` syncs only the files in that directory
     (`cluster.yaml`, `catalog.yaml`). It does not recurse, so `app/`
     and `users-vm/` are not part of it. Wave 0 is the catalog and the
     VKS cluster `music-store`, wave 1 the catalog address, wave 2
     catalog init.
   - `music-store/users-vm` — Application `music-store-dev-vm`. Wave 0
     the users VM, wave 1 the Job that writes `users-service` and
     `postgres-service` into the VKS cluster. No address is in git.
   - `music-store/app` — Application `music-store-dev-app`. The shop in
     namespace `music-store` of that cluster.
4. The incident demo is not an Argo CD Application. After the shop
   answers, `incident-demo/apply.py` fills Zammad, Grafana, the guest
   agent manifests, and the MCP servers. `incident-demo/tanzu-agents/push.py`
   pushes the Cloud Foundry apps. `incident-demo/walk/demo.sh` is the
   incident start, not a deploy step.

## Folders

| Folder | Owner | What it deploys |
|---|---|---|
| `private-ai/` | platform engineer | DSM database, Private AI Services, and the Qwen model. Application `private-ai`. |
| `music-store/` | platform engineer and developer | One shop folder. `cluster.yaml` and `catalog.yaml` are Application `music-store` (the VKS cluster and the DSM catalog). `users-vm/` is Application `music-store-dev-vm`. `app/` is Application `music-store-dev-app`, namespace `music-store`. |
| `incident-demo/` | incident demo | Observability, Zammad, agents and orchestrator, Tanzu push, MCP, PII scrub, CLM, AgentMinder registration, and the walk. Not synced by Argo CD. |

`incident/` at the repository root is an older copy of the demo. It is
not this layout, and it has no `store/` directory.
