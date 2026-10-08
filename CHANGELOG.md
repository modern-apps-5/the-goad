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

### Fixed

- `gitops/private-ai/postgres.yaml`: the VM class is `best-effort-large`.
  DSM refuses a class under 4 CPU for PostgreSQL.

### Changed

- The repository moved from the lab git server to
  `github.com/modern-apps-5/the-goad`. History was kept.

### Not done yet

- OIDC for the org (`terraform/cloud-admin/oidc.tf`) is written and not
  tested. No identity provider is chosen.
- Private AI Services and its models are not in `gitops/` yet.
- The music store application is not deployed by Argo CD yet.
- `docs/walkthrough-script.md` still says the cloud admin creates the
  region. The Terraform reads an existing region.
