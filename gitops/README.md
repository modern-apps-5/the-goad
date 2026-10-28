# gitops

What Argo CD syncs, and nothing else. A commit on `main` is how
`gitops/` changes. Terraform creates the Argo CD Applications. Those
Applications are not edited from this directory.

Each directory belongs to one owner and one Application.

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
     `ClusterSecretStore` in the cluster, once ESO is there, and in
     namespace `platform-tools` the Prometheus agent, the blackbox
     exporter and the `goad-k8s-mcp` service account.
   - `music-store-dev/users-vm/` — Application `music-store-dev-vm`.
     Wave 0 the users VM, wave 1 the Job that writes `users-service` and
     `postgres-service` into the VKS cluster. No address is in git.
   - `music-store-dev/app/` — Application `music-store-dev-app`. The
     shop in namespace `music-store` of that cluster.
   - `platform-tools/` — Application `platform-tools`. The VKS cluster
     `platform-tools` and its ESO addon.
   - `platform-tools-apps/` — Application `platform-tools-apps`. Inside
     that cluster, namespace `incident-tools`: the `ClusterSecretStore`,
     the `ExternalSecret`s, Zammad, Grafana, Prometheus and the blackbox
     exporter. It retries until the cluster and ESO exist.
4. The incident apps: the `platform-engineer` workflow makes their Cloud
   Foundry space, and `tanzu-apps` pushes them. See
   [tanzu/metal-music-app-agentic-system](../tanzu/metal-music-app-agentic-system/README.md).
   Zammad starts empty on a new build. Open
   `http://zammad.goad.gpu.set.lab/#getting_started/auto_wizard` once to
   create the admin user, then make its API token by hand and store it as
   the GitHub secret `INCIDENT_ZAMMAD_TOKEN` before the push.

## Folders

| Folder | Owner | Application | What it deploys |
|---|---|---|---|
| `private-ai/` | platform engineer | `private-ai` | DSM database, Private AI Services, and the Qwen model. |
| `music-store/` | platform engineer | `music-store` | The VKS cluster `music-store`, the DSM catalog, and the ESO addon for the cluster. |
| `music-store-platform/` | platform engineer | `music-store-platform` | Inside the VKS cluster: the `ClusterSecretStore` `secret-store` for Secret Store, and in namespace `platform-tools` what the platform tools cluster needs there: a Prometheus agent and blackbox exporter that write to its Prometheus, and the service account `goad-k8s-mcp`. |
| `platform-tools/` | platform engineer | `platform-tools` | The VKS cluster `platform-tools` and its ESO addon. |
| `platform-tools-apps/` | platform engineer | `platform-tools-apps` | Inside the platform tools cluster, namespace `incident-tools`: Zammad, Grafana with its boards and topology panel, Prometheus and the blackbox exporter, and their `ExternalSecret`s. |
| `music-store-dev/users-vm/` | developer | `music-store-dev-vm` | The users VM, and the Job `shop-endpoints` that writes the users VM's and the catalog's addresses into the VKS cluster. |
| `music-store-dev/app/` | developer | `music-store-dev-app` | The shop's containers, their source, and the `ExternalSecret`s `store-db` and `metal-oracle-model`, in namespace `music-store` of the VKS cluster. |

Directories do not nest across owners. An Application syncs one
directory and does not recurse.

No secret value is in this directory. Terraform writes them to Secret
Store from GitHub secrets, and the placeholder `SUPERVISOR_NAMESPACE` is
replaced by the Application with the generated namespace name (decision
38).

## Host names

Avi DNS answers for `goad.gpu.set.lab`. A name is published by putting it
on the virtual service that owns the address, not by a static record.
For an `avi-lb` Ingress, AKO does that when:

- `spec.rules[].host` is the name;
- the annotation `external-dns.alpha.kubernetes.io/hostname` is the same
  name;
- the annotation `ako.vmware.com/service-engine-group` is `goad-se-group`.

The record's TTL is 30 seconds. That is how `music`, `zammad`, `grafana`
and `prometheus` under `goad.gpu.set.lab` are published. This AKO build
takes one name per Service or Ingress host; a comma-separated list is
refused (`invalid label`). The same DNS profile holds other
organizations' domains. Leave them alone.

To check a name, use `dig @172.21.0.90 <name> A`, then load the page
with that name. A record that only exists in Avi is not a working name.
