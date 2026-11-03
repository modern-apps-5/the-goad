# Platform engineer foundation

The platform engineer's Day 0 Terraform. It logs in to the org the cloud
admin created, never to the provider (System) org, and stops when Argo CD
has something to sync.

It logs in with `vcfa_api_token`: a user API token of the AD service
account `svc.platform_engineer@set.lab` (`auth_type` `api_token`).

| File | What it creates |
|---|---|
| `images.tf` | The org content library `goad-images` and the Ubuntu image in it, for the users VM. The library is attached to every namespace in the org. A `terraform_data` downloads the OVA with `curl` into `.images/` (ignored by git) on the first apply, so that machine or runner needs `curl` and internet access to cloud-images.ubuntu.com. The storage policy is the lab value `content_library_storage_policy`; `ubuntu_image` sets the image name and URL. |
| `namespace.tf` | The Supervisor Namespaces: `platform` for Argo CD, `private-ai` for Private AI Services and its database, `music-store` for the shop's users VM, catalog, and VKS cluster, and `platform-tools` for the VKS cluster of the incident demo's tools. |
| `argocd.tf` | The Argo CD instance, from `manifests/argocd.yaml`, and the role its service account needs. |
| `pais.tf` | The Secret with the Private AI Services administrator. Everything else for Private AI Services is in `gitops/private-ai/`. |
| `secrets.tf` | `KeyValueSecret`s in Secret Store (decision 38). In `music-store`: the catalog password and the chat's model key, from the GitHub secrets `MUSIC_STORE_DB_PASSWORD` and `MUSIC_STORE_CHAT_API_KEY`. In `platform-tools`: Grafana's and Zammad's passwords, from `INCIDENT_GRAFANA_ADMIN_PASSWORD`, `INCIDENT_ZAMMAD_DB_PASSWORD` and `INCIDENT_ZAMMAD_ADMIN_PASSWORD`, and the blackbox exporter's Qwen check, from `INCIDENT_QWEN_API_KEY`. Empty values skip them. In `platform-tools`, for the image build: `platform-tools-harbor-push`, the registry robot's login, from `MUSIC_STORE_HARBOR_ROBOT_SECRET` (variable `music_store_robot_secret`), and `platform-tools-git-deploy-key`, the key the build clones the repository with. |
| `gitops.tf` | The handoff: for each namespace other than `platform`, its registration with Argo CD and one Application; the music store's cluster registration and the Applications `music-store-platform` and `music-store-apps`; the platform tools cluster's registration and the Applications `platform-tools-apps` and `platform-tools-builds`; and the patches that put the generated namespace and cluster names into the manifests. |
| `tanzu.tf` | On Tanzu Platform, org `Goad`: the space `metal-music-app-agentic-system` and the user-provided services `goad-qwen` and `k8s-mcp-cluster` (decision 40). The agents' `sc-*` services moved to [terraform/agentic-ops](../agentic-ops) (decision 50). `tanzu.tf` has a `removed` block for each, with `destroy = false`. Remove them once the change is in every state. The provider logs in with `CF_ACCESS_TOKEN`, a token for `goad-deployer` that the `cf-token` action gets. |

It uses the org's default project and default VPC. It does not create the
Avi Service Engine Group: the namespaces only name it
(`service_engine_group_name`). `terraform/cloud-admin/org-config` creates
it. Destroy this root before `org-config`, because the namespaces use the
group.

## Apply

Apply `terraform/cloud-admin/org` and `terraform/cloud-admin/org-config`
first. `org-config` imports `svc.platform_engineer@set.lab` into the org.

Make the API token once, by hand: log in to the org `goad` with VCF SSO
as that user, then User Preferences, API Tokens. Put it in
`terraform.tfvars` as `vcfa_api_token`. A new AD user can log in only
after the Identity Broker syncs the directory (VCF Operations, Fleet
Management, Identity & Access, VCF SSO). If the demo is built, copy the
team's file.

It is not a VCF Automation service account. A service account's session
cannot manage other service accounts (403 `SERVICE_ACCOUNT_SIMPLE_VIEW`),
and the Argo CD step in `argocd.tf` needs that. A user API token session
can.

```sh
cp terraform.tfvars.example terraform.tfvars   # secrets only; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
export CF_ACCESS_TOKEN=<a Tanzu Platform token for goad-deployer>
terraform init -backend-config=backend.hcl
terraform apply
```

`CF_ACCESS_TOKEN` is for `tanzu.tf`. The foundation accepts only the
`goad-deployer` app's client assertion, which the Cloud Foundry provider
cannot sign, so the token is fetched first. In GitHub the `cf-token`
action does it.

## The handoff

Namespace names are generated, for example `private-ai-hphfz`, so git
cannot name them. Terraform knows them. For the namespace with key
`private-ai`, Terraform creates:

- a `ManagedEntity`, which registers the namespace with Argo CD as the
  cluster `private-ai`;
- an `Application` named `private-ai`, which syncs `gitops/private-ai/`
  into the namespace.

Manifests under `gitops/` do not set a namespace. To give Argo CD another
namespace, add it to `namespaces` and add the directory `gitops/<key>/`.

The rest of the music store has its own handoff. The developer writes
the shop's code, and the platform engineer deploys it (decision 45).
Terraform creates:

- a `ManagedEntity` named `music-store-cluster`, which registers the VKS
  cluster with Argo CD. The cluster name comes from
  `gitops/music-store/cluster.yaml`;
- an `Application` named `music-store-platform`, which syncs
  `gitops/music-store-platform/` into the VKS cluster: the platform
  engineer's part inside it;
- an `Application` named `music-store-apps`, which syncs
  `gitops/music-store-apps/` into the namespace `music-store` of the
  VKS cluster.

These Applications retry, because they depend on the cluster and the
catalog that the Application `music-store` builds.

The platform tools cluster has the same kind of handoff: a `ManagedEntity`
named `platform-tools-cluster`, for the cluster that
`gitops/platform-tools/cluster.yaml` names, and the Application
`platform-tools-apps`, which syncs `gitops/platform-tools-apps/` into its
namespace `incident-tools` (decision 42). A second Application,
`platform-tools-builds`, syncs `gitops/platform-tools-builds/` into the
namespace `music-store-builds` of the same cluster: the Tekton pipeline
that builds the music store's images (decision 48).

Argo CD reads the repository with a read-only deploy key. The private
half stays in `.secrets/`, which git ignores.

The key is shared by the team, and so is `terraform.tfvars`. Terraform
writes the key and the Private AI Services password hash into Secrets,
the music store's and the platform tools' passwords and keys into Secret
Store, and the incident apps' keys into Cloud Foundry services.
If you apply with a key or a hash of your own, Terraform replaces the
team's, and Argo CD can no longer read git. Copy both files from a
teammate. `docs/terraform-state.md` has the list.

## Which provider applies what

- `kubectl_manifest`: every Kubernetes object. The org API has a fixed
  address. The platform namespace's API address is known only during
  apply, and `lazy_load = true` lets the provider plan without it.
- `terracurl`: the service account role. Roles belong to the VCF
  Automation REST API, not to Kubernetes.
- Not `kubernetes_manifest`: the org API publishes no OpenAPI schema for
  these kinds, and it fails with "resource not found in OpenAPI index".
- Read a namespace's name from `local.namespace_names`, never straight
  from the namespace resource. It keeps the plan working when a
  namespace is added or resized. `namespace.tf` says why.

## Argo CD login

The instance has a load balancer address, and with that the service
registers it with VCF Automation as an OIDC client. Users of the org log
in with "VCF Automation". `manifests/argocd.yaml` sets what they can do:
members of the group `ans-platform-engineer@set.lab` have `role:admin`.
On the first deploy the UI answers only after Avi has started the
Service Engines.
