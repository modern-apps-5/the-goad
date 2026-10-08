# Changelog

What changed in this repository, newest first. The reasons are in
[docs/decisions.md](docs/decisions.md).

## 2026-10-08 later

### Added

- `gitops/music-store/users-vm.yaml`: the shop users service as a VM
  Service VM. Login `admin` / `admin`. Service name `users-service`.
  No namespace and no address.
- `gitops/music-store/catalog.yaml`: the shop catalog as a DSM
  `PostgresCluster`, a Service named `postgres-service`, and the Jobs
  that publish DSM's address and load the six albums.
- `terraform/platform-engineer`: a `music-store` namespace so Argo CD
  syncs `gitops/music-store/`.

### Changed

- `terraform/*/backend.tf`: the state address and settings are now in
  git. `backend.hcl` holds only the token.

- `terraform/*/lab.auto.tfvars`: the lab values that are not secret are
  now in git. `terraform.tfvars` holds secrets only.

- `docs/terraform-state.md`, `README.md`: the deploy key,
  `terraform.tfvars`, and the password hash are shared by the team. The
  documents say so, and say what breaks when someone applies with their
  own.

- `docs/execution-plan.md` and `docs/walkthrough-script.md`: each has a
  dated note of what has changed since it was written. Their original
  text is kept.

- `app/music-store` chat sets `OPENAI_TLS_VERIFY=false` and documents
  the model secret. The secret is still not in git.

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
- `gitops/private-ai/database-service.yaml`: a fixed Service name for
  the Private AI database, and the Job that points it at the address DSM
  assigns. The address is no longer in git.
- `terraform/platform-engineer/manifests/argocd.yaml`: health checks for
  a DSM `PostgresCluster`, a `PAISConfiguration`, and a `ModelEndpoint`.
  Argo CD shows each as progressing until its `Ready` condition is true.
- `gitops/private-ai/`: sync waves. Database and its Service, then the
  Job that points the Service at the database, then Private AI Services,
  then the model.

### Fixed

- `terraform/platform-engineer`: adding or resizing a namespace made the
  plan fail with "dial tcp 127.0.0.1:80: connection refused". Namespace
  names are now read through one local value, so the kubeconfig lookups
  are not put off until apply.
- `gitops/private-ai/postgres.yaml`: the VM class is `best-effort-large`.
  DSM refuses a class under 4 CPU for PostgreSQL.

### Changed

- Terraform state for both roots moved from local files to the lab's
  Gitea, through the `http` backend. `backend.hcl.example` shows the
  settings, and `docs/terraform-state.md` the setup.

- `README.md`: a quickstart from an empty org to a served model, the
  repository layout, and teardown.
- The repository moved from the lab git server to
  `github.com/modern-apps-5/the-goad`. History was kept.

### Not done yet

- OIDC for the org (`terraform/cloud-admin/oidc.tf`) is written and not
  tested. No identity provider is chosen.
- The embeddings model is not in `gitops/` yet. Only Qwen is.
- No inference request has been sent to Qwen yet.
- The quickstart in `README.md` has not been run from top to bottom, and
  a full teardown has not been tested since Private AI Services was
  added.
- Security admin, developer, and the IT Ops agents are not started.
- The store, cart, orders, and chat containers are not deployed by
  Argo CD yet. The users VM and the catalog are.
- `docs/walkthrough-script.md` is not rewritten. It now lists where it
  differs from what is built.
