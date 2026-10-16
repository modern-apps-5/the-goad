# Changelog

What changed in this repository, newest first. The reasons are in
[docs/decisions.md](docs/decisions.md).

## 2026-10-15 (music store cluster)

### Added

- The music store's VKS cluster `music-store`, in
  `gitops/music-store/cluster.yaml`. Argo CD syncs it with the Application
  `music-store`. One control plane and two workers, Kubernetes
  v1.36.2+vmware.2. The containers in `app/music-store` are not deployed
  onto it yet.
- The `music-store` namespace limits are now 40000M CPU, 48Gi memory, and
  150Gi storage (`terraform/platform-engineer/variables.tf`), to fit the
  cluster. It needs a platform engineer apply. The plan shows an in-place
  change to the music-store namespace.
- The org content library `goad-images`, with the Ubuntu 24.04 cloud image
  `ubuntu-24.04-cloud`, in `terraform/platform-engineer/images.tf`. The
  library is attached to every namespace in the org. It needs a platform
  engineer apply. The first apply downloads about 570 MiB with `curl`, so
  the machine or runner needs internet access to cloud-images.ubuntu.com.
  The new lab value is `content_library_storage_policy`.

### Fixed

- The users VM in `gitops/music-store` never came up. The org had no VM
  image, and the className `best-effort-xsmall` is not offered by the org.
  The className is now `best-effort-small`, and the image comes from
  `images.tf`.

## 2026-10-15 (AgentMinder)

### Added

- `terraform/cloud-admin/agentminder`, a third cloud admin root (state
  `goad-cloud-admin-agentminder`). It installs AgentMinder with Helm on
  the VKS cluster that `org-config` made: `ingress-nginx` 4.15.1,
  `infra-ssp`, and `ssp` (chart version 4.1.1+1673). It is installed
  small: demo size, one Hazelcast member, `aigateway` and `mcpserver` on,
  the rest off. It reads `org-config`'s state, so on a machine also
  `export TF_HTTP_PASSWORD=<the state token>`. The hostname
  `agentminder.goad.gpu.set.lab` gets its DNS record from Avi: AKO
  serves the ingress controller's Service and puts the external-dns
  hostname on the virtual service.
- `terraform/cloud-admin/org-config`: the project `cloud-admin`, the
  Supervisor Namespace `agentminder-xxxxx` in it, and the VKS cluster
  `agentminder`. New inputs `region_name`, `zone_name`, `vpc_name`,
  `storage_class_name`, `service_engine_group_name`,
  `cloud_admin_project`, and `agentminder_cluster`. New outputs
  `cloud_admin_project`, `agentminder_namespace`, and
  `agentminder_cluster_name`.
- `.github/workflows/cloud-admin.yml`: a third job, `agentminder`, after
  `org-config`. New repository secrets `SSP_REGISTRY_USERNAME` and
  `SSP_REGISTRY_PASSWORD`.
- `terraform/cloud-admin/agentminder/README.md`.
- `docs/decisions.md`: decisions 29 and 30.

### Changed

- The org's Service Engine Group `goad-se-group` moved from
  `terraform/platform-engineer` to `terraform/cloud-admin/org-config`.
  The AgentMinder namespace needs it, and the cloud admin runs first.
  A one-shot `import` block in `org-config` and `removed` blocks with
  `destroy = false` in `terraform/platform-engineer` moved it between
  states without deleting it. Both were applied in the lab and are gone
  from the code. Teardown order:
  platform engineer, `agentminder`, `org-config`, `org`. Decision 6 is
  amended.
- `README.md`, `docs/terraform-state.md`, `docs/execution-plan.md`, and
  the READMEs of `org-config` and `platform-engineer` follow the above.

## 2026-10-15

### Changed

- The cloud admin is now two Terraform roots, run in order.
  `terraform/cloud-admin/` moved to `terraform/cloud-admin/org/` (stage 1:
  creates the org; the state is still `goad-cloud-admin`). The new
  `terraform/cloud-admin/org-config/` is stage 2: it configures things
  inside the org (state `goad-cloud-admin-org-config`). Teammates move
  their ignored `backend.hcl` and `terraform.tfvars` into `org/`, run
  `terraform init -backend-config=backend.hcl` there again, and set up
  `org-config/` the same way. Teardown order: platform engineer, then
  `org-config`, then `org`.
- The org's one local user is now `cloud-admin`, an Organization
  Administrator, made by stage 1 with `cloud_admin_password`. The local
  user `platform-admin` is deleted. VCF Automation allows one local user
  for each org.
- `terraform/platform-engineer` logs in with `vcfa_api_token`, a user API
  token of `svc.platform_engineer@set.lab`, made by hand once in the UI.
  It is not a VCF Automation service account: a service account's session
  cannot manage other service accounts (403 `SERVICE_ACCOUNT_SIMPLE_VIEW`),
  and the Argo CD step in `argocd.tf` needs that.
- Argo CD: `role:admin` is now for `william.arroyo@set.lab`, not
  `platform-admin` (`terraform/platform-engineer/manifests/argocd.yaml`).
- `.github/workflows/cloud-admin.yml` has two jobs, `org` then
  `org-config`. `platform-engineer.yml` passes
  `PLATFORM_ENGINEER_VCFA_TOKEN` as `TF_VAR_vcfa_api_token`.
- `README.md`, `docs/terraform-state.md`, `docs/decisions.md`, and the
  READMEs of the roots follow all of the above.

### Added

- VCF SSO for the org, in stage 1. `oidc.tf` creates the org's OIDC client
  in the VCF Identity Broker through VCF Operations' internal, unsupported
  API (`/suite-api/internal/vidb/oauthclients`), then sets
  `vcfa_org_oidc`. People sign in with their AD account. New variables:
  `cloud_admin_username`, `cloud_admin_password`, `ops_password`,
  `ops_url`, `vidb_hostname`, and `vcf_sso`.
- `terraform/cloud-admin/org-config`: `users.tf` imports VCF SSO users
  into the org. Platform engineers (`platform_engineers`) get the org role
  Organization User and admin of the project `default-project`, through a
  ProjectRoleBinding. The AD service account
  `svc.platform_engineer@set.lab` is imported as Organization
  Administrator.
- `terraform/cloud-admin/org-config/README.md`.
- Repository secrets `CLOUD_ADMIN_PASSWORD`, `OPS_ADMIN_PASSWORD`, and
  `PLATFORM_ENGINEER_VCFA_TOKEN`.
- `docs/decisions.md`: decisions 26, 27, and 28.

### Removed

- The variables `org_admin_username` and `org_admin_password` of the cloud
  admin, and `vcfa_password` of the platform engineer.
- The repository secret `ORG_ADMIN_PASSWORD`. It stays until this change
  is merged, then it is deleted.

## 2026-10-12

### Fixed

- The runner's pods had about 250 MB of disk, and `terraform init` in a
  workflow failed with `no space left on device`. The fix is in
  supervisor-github-runner: a pod now asks for 4 GB, deleted with the
  pod. `runner_commit` in `terraform/runner` points at that commit. Both
  workflows then planned with no changes.

### Added

- `.github/workflows/cloud-admin.yml` and `platform-engineer.yml`: one
  workflow for each persona. Each runs its own Terraform root when a
  person starts it: a plan, and an apply if asked for, on `main` only.
  Nothing runs on a pull request or a push yet. Both run on the lab's
  self-hosted runner.
- `terraform/runner`: a third Terraform root, applied by hand, that
  builds that runner. The Supervisor Namespace `goad-runner`, made in
  vCenter, and in it the Secret and a Deployment of two replicas
  registered to the organization. Its state is `goad-runner` in Gitea.
- `scripts/create-github-app.py`: creates the GitHub App that the
  runner logs in with. Run by a person, once.
- `docs/decisions.md`: decision 25, why the runner is there.
- `README.md`: how to start a workflow. `docs/terraform-state.md`: the
  runner root's two secrets, and that the repository secrets in GitHub
  are one more copy of the shared values.

## 2026-10-09

### Added

- `README.md`: a diagram of the automation flow, from the cloud admin's
  Terraform to the Argo CD sync waves.

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

- `README.md`: a section for joining a demo that is already built.

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
