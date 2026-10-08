# Platform engineer foundation

The platform engineer's Day 0 Terraform. It logs in to the org the cloud
admin created, never to the provider (System) org, and stops when Argo CD
has something to sync.

| File | What it creates |
|---|---|
| `avi.tf` | The org's Avi Service Engine Group. |
| `namespace.tf` | The Supervisor Namespaces: `platform` for Argo CD, `private-ai` for Private AI Services and its databases. |
| `argocd.tf` | The Argo CD instance, from `manifests/argocd.yaml`, and the role its service account needs. |
| `pais.tf` | The Secret with the Private AI Services administrator. Everything else for Private AI Services is in `gitops/private-ai/`. |
| `gitops.tf` | The handoff: for each namespace other than `platform`, its registration with Argo CD and one Application. |

It uses the org's default project and default VPC.

## Apply

Apply `terraform/cloud-admin` first.

```sh
cp terraform.tfvars.example terraform.tfvars   # then fill in
cp backend.hcl.example backend.hcl             # then fill in
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

Argo CD reads the repository with a read-only deploy key. The private
half stays in `.secrets/`, which git ignores.

## Which provider applies what

- `kubectl_manifest`: every Kubernetes object. The org API has a fixed
  address. The platform namespace's API address is known only during
  apply, and `lazy_load = true` lets the provider plan without it.
- `terracurl`: the service account role. Roles belong to the VCF
  Automation REST API, not to Kubernetes.
- Not `kubernetes_manifest`: the org API publishes no OpenAPI schema for
  these kinds, and it fails with "resource not found in OpenAPI index".
- No `wait_for` on the Service Engine Group: it waits with a watch, and
  an organization administrator cannot watch that kind.

## Argo CD login

The instance has a load balancer address, and with that the service
registers it with VCF Automation as an OIDC client. Users of the org log
in with "VCF Automation". `manifests/argocd.yaml` sets what they can do.
On the first deploy the UI answers only after Avi has started the
Service Engines.
