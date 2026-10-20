# Platform engineer foundation

The platform engineer's Day 0 Terraform. It logs in to the org the cloud
admin created, never to the provider (System) org, and stops when Argo CD
has something to sync.

It logs in with `vcfa_api_token`: a user API token of the AD service
account `svc.platform_engineer@set.lab` (`auth_type` `api_token`).

| File | What it creates |
|---|---|
| `images.tf` | The org content library `goad-images` and the Ubuntu image in it, for the users VM. The library is attached to every namespace in the org. A `terraform_data` downloads the OVA with `curl` into `.images/` (ignored by git) on the first apply, so that machine or runner needs `curl` and internet access to cloud-images.ubuntu.com. The storage policy is the lab value `content_library_storage_policy`; `ubuntu_image` sets the image name and URL. |
| `namespace.tf` | The Supervisor Namespaces: `platform` for Argo CD, `private-ai` for Private AI Services and its database, `music-store` for the shop's users VM, catalog, and VKS cluster. |
| `argocd.tf` | The Argo CD instance, from `manifests/argocd.yaml`, and the role its service account needs. |
| `pais.tf` | The Secret with the Private AI Services administrator. Everything else for Private AI Services is in `gitops/private-ai/`. |
| `gitops.tf` | The handoff: for each namespace other than `platform`, its registration with Argo CD and one Application. |

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
terraform init -backend-config=backend.hcl
terraform apply
```

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

The developer's part of the music store has its own handoff. Terraform
creates:

- a `ManagedEntity` named `music-store-cluster`, which registers the VKS
  cluster with Argo CD. The cluster name comes from
  `gitops/music-store/cluster.yaml`;
- an `Application` named `music-store-dev-vm`, which syncs
  `gitops/music-store-dev/users-vm/` into the `music-store` namespace;
- an `Application` named `music-store-dev-app`, which syncs
  `gitops/music-store-dev/app/` into the namespace `music-store` of the
  VKS cluster.

Both Applications retry, because they depend on the cluster and the
catalog that the Application `music-store` builds.

Argo CD reads the repository with a read-only deploy key. The private
half stays in `.secrets/`, which git ignores.

The key is shared by the team, and so is `terraform.tfvars`. Terraform
writes the key and the Private AI Services password hash into Secrets.
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
