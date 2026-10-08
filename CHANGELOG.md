# Changelog

What changed in this repository, newest first. The reasons are in
[docs/decisions.md](docs/decisions.md).

## 2026-10-08

### Added

- `terraform/cloud-admin`: the cloud admin's Terraform. It creates the
  org, its first organization administrator, the region quota, the org
  networking settings, and the regional networking setting on the
  region's Distributed VLAN Connection.
- `terraform/cloud-admin`: the org's DSM data service policy for
  PostgreSQL.
- `terraform/cloud-admin`: the Avi load balancer setting for the org,
  tenant managed.
- `terraform/cloud-admin`: a CPU and memory reservation in the org's
  region quota.
- `terraform/platform-engineer`: the platform engineer's Terraform. It
  creates the org's Avi Service Engine Group, the Supervisor Namespaces
  `platform` and `private-ai`, and the Argo CD instance.
- `terraform/platform-engineer`: the handoff to Argo CD. For each
  namespace other than `platform`, a `ManagedEntity` and one
  `Application` that syncs `gitops/<key>/`.
- `terraform/platform-engineer`: a read-only deploy key gives Argo CD
  access to this repository.
- `gitops/private-ai/postgres.yaml`: the DSM `PostgresCluster` for
  Private AI Services.
- `gitops/private-ai/pais.yaml`: Private AI Services and one model, Qwen
  2.5 1.5B on CPU.
- `terraform/platform-engineer/pais.tf`: the Secret with the Private AI
  Services administrator.
- `terraform/platform-engineer/manifests/argocd.yaml`: health checks for
  a DSM `PostgresCluster`, a `PAISConfiguration`, and a `ModelEndpoint`.
  Argo CD shows each as progressing until its `Ready` condition is true.
- `gitops/private-ai/`: sync waves. Database, then Private AI Services,
  then the model.

### Fixed

- `gitops/private-ai/postgres.yaml`: the VM class is `best-effort-large`.
  DSM refuses a class under 4 CPU for PostgreSQL.

### Changed

- The repository moved from the lab git server to
  `github.com/modern-apps-5/the-goad`. History was kept.

### Not done yet

- OIDC for the org (`terraform/cloud-admin/oidc.tf`) is written and not
  tested. No identity provider is chosen.
- The embeddings model is not in `gitops/` yet. Only Qwen is.
- The music store application is not deployed by Argo CD yet.
- `docs/walkthrough-script.md` still says the cloud admin creates the
  region. The Terraform reads an existing region.
