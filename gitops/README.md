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
3. Argo CD, in this order. The applications do not wait on each
   other. `music-store-platform` and `music-store-apps` need the
   cluster and the catalog from `music-store`, and retry until they
   exist.
   - `private-ai/` — Application `private-ai`. Wave 0 database and the
     ingress certificate from the GOAD CA, wave 1 the address Job, wave 2
     Private AI Services, wave 3 model `qwen-14b-xlarge` and the Gateway
     that names it `pais.goad.gpu.set.lab`.
   - `music-store/` — Application `music-store`. Wave 0 is the catalog,
     the VKS cluster `music-store`, its ESO and cert-manager addons,
     Antrea's NSX integration, and the users VM, wave 1 the catalog address, wave 2 catalog init, which
     reads the password from Secret Store, wave 3 the Job
     `shop-endpoints`, which writes `users-service` and
     `postgres-service` into the VKS cluster. Argo CD holds wave 3 until
     the cluster is healthy. No address is in git.
   - `music-store-platform/` — Application `music-store-platform`. The
     `ClusterSecretStore` in the cluster, once ESO is there; the
     self-signed `ClusterIssuer` and wildcard `Certificate` for the
     shop's Gateway, in namespace `default`; and in namespace
     `platform-tools` the Prometheus agent, the blackbox exporter and the
     `goad-k8s-mcp` service account.
   - `music-store-apps/` — Application `music-store-apps`. The
     shop in namespace `music-store` of that cluster.
   - `platform-tools/` — Application `platform-tools`. The VKS cluster
     `platform-tools`, its ESO addon, and its Tekton addon.
   - `platform-tools-apps/` — Application `platform-tools-apps`. Inside
     that cluster, namespace `incident-tools`: the `ClusterSecretStore`,
     the `ExternalSecret`s, Zammad, Grafana, Prometheus and the blackbox
     exporter. It retries until the cluster and ESO exist.
   - `platform-tools-builds/` — Application `platform-tools-builds`.
     Inside that cluster, namespace `music-store-builds`: the Tekton
     pipeline and tasks that build the music store's images, the
     registry and Git credentials, and the Dockerfile template. It
     retries until Tekton exists.
4. Security admin Terraform: `terraform/security-admin`, once the
   cluster `music-store` is up with Antrea's NSX integration. It puts
   the vDefend policy in NSX, which pushes it into the cluster
   (decision 49).
5. The incident apps: the `platform-engineer` workflow makes their Cloud
   Foundry space, the `agentic-ops` workflow makes their AgentMinder
   clients in it, and `tanzu-apps` pushes them. See
   [tanzu/metal-music-app-agentic-system](../tanzu/metal-music-app-agentic-system/README.md).
   Zammad starts empty on a new build. One
   `curl http://zammad.goad.gpu.set.lab/api/v1/getting_started/auto_wizard`
   creates the admin user from Secret Store, then make its API token by hand and store it as
   the GitHub secret `INCIDENT_ZAMMAD_TOKEN` before the push.

## Folders

| Folder | Owner | Application | What it deploys |
|---|---|---|---|
| `private-ai/` | platform engineer | `private-ai` | DSM database, Private AI Services, the Qwen model, and the Gateway and certificate that make it `pais.goad.gpu.set.lab`. |
| `music-store/` | platform engineer | `music-store` | The VKS cluster `music-store`, the DSM catalog, the ESO and cert-manager addons for the cluster, Antrea's NSX integration, the users VM, and the Job `shop-endpoints` that writes the users VM's and the catalog's addresses into the VKS cluster. |
| `music-store-platform/` | platform engineer | `music-store-platform` | Inside the VKS cluster: the `ClusterSecretStore` `secret-store` for Secret Store, the Gateway's certificate, and in namespace `platform-tools` what the platform tools cluster needs there: a Prometheus agent and blackbox exporter that write to its Prometheus, and the service account `goad-k8s-mcp`; the shop's default deny (decision 49); and in namespace `pen-test` the always-on pen test's blackbox exporter, for the board "Pen test". |
| `platform-tools/` | platform engineer | `platform-tools` | The VKS cluster `platform-tools`, its ESO addon, and its Tekton addon. |
| `platform-tools-apps/` | platform engineer | `platform-tools-apps` | Inside the platform tools cluster, namespace `incident-tools`: Zammad, Grafana with its boards and topology panel, Prometheus and the blackbox exporter, and their `ExternalSecret`s. |
| `platform-tools-builds/` | platform engineer | `platform-tools-builds` | Inside the platform tools cluster, namespace `music-store-builds`: the Tekton pipeline and tasks that build the music store's images from `apps/music-store/`, the registry and Git credentials, and the Dockerfile template `dockerfiles/python`. |
| `music-store-apps/` | platform engineer; the developer's code is in `apps/music-store/` | `music-store-apps` | The shop's containers, from the images built from `apps/music-store/` (their tag in `kustomization.yaml`), the `ExternalSecret`s `store-db` and `metal-oracle-model`, and the HTTPRoute and WAF L7Rule, in namespace `music-store` of the VKS cluster; and the Gateway `metal-store`, in namespace `default`; and the Antrea policy for the calls between the shop's services (decision 49). |

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

The record's TTL is 30 seconds. That is how `zammad`, `grafana` and
`prometheus` under `goad.gpu.set.lab` are published.

The shop, `music.goad.gpu.set.lab`, uses Gateway API instead (decision
43): the Gateway `metal-store` in namespace `default` listens for
`*.goad.gpu.set.lab`, and the HTTPRoute `metal-store-frontend` names the
host. Its HTTPS certificate is the Secret
`default/https-goad.gpu.set.lab-cert`, which cert-manager makes from
`music-store-platform/gateway-cert.yaml`. The L7Rule `metal-store-waf`
puts Avi's `System-WAF-Policy` on the route; a HostRule does nothing for
a Gateway.

Private AI Services, `pais.goad.gpu.set.lab`, is in a Supervisor
Namespace, not a VKS cluster. Its LoadBalancer Service is NSX's, which
publishes no name, annotation or not. A Gateway of class `avi-lb` in the
namespace is the Supervisor's Avi controller, and its HTTPRoute's
hostname is published like the shop's (decision 53,
`private-ai/ingress.yaml`). The listener's hostname alone publishes
nothing.

This AKO build
takes one name per Service or Ingress host; a comma-separated list is
refused (`invalid label`). The same DNS profile holds other
organizations' domains. Leave them alone.

To check a name, use `dig @172.21.0.90 <name> A`, then load the page
with that name. A record that only exists in Avi is not a working name.
