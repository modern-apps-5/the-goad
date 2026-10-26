# gitops

What Argo CD syncs, and nothing else. A commit on `main` is how
`gitops/` changes. Terraform creates the Argo CD Applications. Those
Applications are not edited from this directory.

Each directory belongs to one owner and one Application. The incident
demo is run by a person, so it is at the repository root in
[incident-demo](../incident-demo), not here.

## Deploy order

1. Cloud admin Terraform: `terraform/cloud-admin/org`, then
   `terraform/cloud-admin/org-config`, then
   `terraform/cloud-admin/agentminder`.
2. Platform engineer Terraform: `terraform/platform-engineer`. That
   creates the Supervisor Namespaces, Argo CD, and the Applications
   that point at the directories below.
3. Argo CD, in this order. The platform applications do not wait on
   each other. The developer applications need the cluster and the
   catalog from `music-store`, and retry until they exist.
   - `private-ai/` — Application `private-ai`. Wave 0 database, wave 1
     the address Job, wave 2 Private AI Services, wave 3 model
     `qwen-14b-xlarge`.
   - `music-store/` — Application `music-store`. Wave 0 is the catalog,
     the VKS cluster `music-store` and the ESO addon, wave 1 the catalog
     address, wave 2 catalog init, which reads the password from Secret
     Store.
   - `music-store-platform/` — Application `music-store-platform`. The
     `ClusterSecretStore` in the cluster, once ESO is there.
   - `music-store-dev/users-vm/` — Application `music-store-dev-vm`.
     Wave 0 the users VM, wave 1 the Job that writes `users-service` and
     `postgres-service` into the VKS cluster. No address is in git.
   - `music-store-dev/app/` — Application `music-store-dev-app`. The
     shop in namespace `music-store` of that cluster.
4. The incident demo, by hand, after the shop answers: see
   [incident-demo/README.md](../incident-demo/README.md).

## Folders

| Folder | Owner | Application | What it deploys |
|---|---|---|---|
| `private-ai/` | platform engineer | `private-ai` | DSM database, Private AI Services, and the Qwen model. |
| `music-store/` | platform engineer | `music-store` | The VKS cluster `music-store`, the DSM catalog, and the ESO addon for the cluster. |
| `music-store-platform/` | platform engineer | `music-store-platform` | Inside the VKS cluster: the `ClusterSecretStore` `secret-store` for Secret Store. |
| `music-store-dev/users-vm/` | developer | `music-store-dev-vm` | The users VM, and the Job `shop-endpoints` that writes the users VM's and the catalog's addresses into the VKS cluster. |
| `music-store-dev/app/` | developer | `music-store-dev-app` | The shop's containers, their source, and the `ExternalSecret`s `store-db` and `metal-oracle-model`, in namespace `music-store` of the VKS cluster. |

Directories do not nest across owners. An Application syncs one
directory and does not recurse.

No secret value is in this directory. Terraform writes them to Secret
Store from GitHub secrets, and the placeholder `SUPERVISOR_NAMESPACE` is
replaced by the Application with the generated namespace name (decision
38).
