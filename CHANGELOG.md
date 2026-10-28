# Changelog

What changed in this repository, newest first. The reasons are in
[docs/decisions.md](docs/decisions.md).

## 2026-10-28 (Tanzu apps, one CLI install)

### Changed

- `tanzu-apps.yml` installs the cf CLI and its plugins once, in a new `cli`
  job, and gives them to the push jobs as an artifact. Each push job's cf
  login took from 26 seconds to almost 7 minutes when it installed the
  plugins itself. `cf-login` skips the download when the CLI is already in
  place, and has a `login: "false"` mode for the `cli` job.
- The runners have 4 CPU and 8Gi (`runner_resources` in `terraform/runner`;
  upstream gives 2 CPU and 2Gi). The cf CLI's first run builds a command
  cache by starting its plugin once per command, dozens at a time, which
  ran out of memory and got pods evicted. Applied by hand on 2026-10-28.
  With both changes, the CLI install takes 18 seconds once per run and a
  push job's login about 1 second. Whether the CLI can skip that cache is
  issue #42.

## 2026-10-27 (Tanzu apps, one job per app)

### Changed

- `tanzu-apps.yml` pushes each app in its own job, so each push has its
  own log and a failed app does not stop the others. The network policies
  are a last job, after every push.
- `platform-engineer.yml` gets its Cloud Foundry token from the new
  `.github/actions/cf-token`, which signs goad-deployer's client assertion
  with `openssl`. It no longer installs the cf CLI, whose first run installs
  about 140 MB of plugins and got a runner pod evicted for memory pressure.
- `cf-login` puts the CLI's `HOME` on the runner's work disk.

## 2026-10-27 (Tanzu apps workflow)

### Added

- `tanzu/metal-music-app-agentic-system/`: the incident demo's nine Cloud
  Foundry apps, one directory each, with `manifest.yml` and `stage.sh`
  (decision 40). The sources came from `incident-demo/mcp`, `pii`,
  `agents/orchestrator`, `agents/roles`, the agents' skills, and
  `tanzu-agents/sidecar` and `trust`.
- `.github/workflows/tanzu-apps.yml`: pushes them on every change on
  `main`. Needs the `INCIDENT_*` GitHub secrets.
- `.github/actions/cf-login`: installs the cf CLI from the foundation and
  logs in as `goad-deployer`.
- `terraform/platform-engineer/tanzu.tf`: the space and its six
  user-provided services, imported. New variables `incident_qwen_api_key`,
  `incident_k8s_token`, `incident_sidecar_token`, and provider
  `cloudfoundry/cloudfoundry`.

### Removed

- `incident-demo/tanzu-agents/` (`push.py` and the four manifests).

## 2026-10-27 (AgentMinder SDK mirror)

### Added

- `scripts/mirror-agentminder-sdk.sh`: puts Broadcom's AgentMinder Python
  SDK wheel in the private package `ghcr.io/modern-apps-5/agentminder-sdk`,
  tagged with the build (`4.1.1.1673`) and the release (`4.1.1`). The SDK
  is not on public PyPI, and the workflow runner has no Docker and no
  lasting Broadcom registry token, so workflows pull the wheel from GitHub
  with `GITHUB_TOKEN`. Run it again with the new SDK when AgentMinder is
  upgraded. 4.1.1.1673 is pushed.

## 2026-10-27 (incident demo)

### Removed

- `incident/`, the earlier incident design on cluster `goad-store`. It was
  never applied, and `incident-demo/` replaced it (decision 39). Git
  history has it.

### Changed

- The AgentMinder sidecar (`mcp_bridge.py`, `run-sidecar.sh`) and its test
  moved to `incident-demo/tanzu-agents/sidecar/`. `push.py` reads them from
  there instead of from a checkout under `/tmp`.

## 2026-10-26 (gitops layout)

### Changed

- The developer's directories are `gitops/music-store-dev/app` and
  `gitops/music-store-dev/users-vm` again (decision 37). The Applications
  `music-store-dev-app` and `music-store-dev-vm` point there, and the
  Application `music-store` no longer sets `directory.recurse`. Run the
  platform engineer Terraform after the merge.
- The incident demo moved from `gitops/incident-demo` to `incident-demo`
  at the repository root. Argo CD does not sync it.
- `app/music-store` is described as the earlier shape. It is not deployed.
- `catalog-init` reads the `music_user` password from Secret Store through
  the Supervisor's vault injector, and sets it on every sync.
- `gitops/music-store` is a kustomization, so that its Application can
  patch in the namespace name.

### Added

- Secrets from GitHub to Secret Store to ESO (decision 38):
  `terraform/platform-engineer/secrets.tf` writes the KVs
  `music-store-catalog` and `music-store-chat` from the new GitHub secrets
  `MUSIC_STORE_DB_PASSWORD` and `MUSIC_STORE_CHAT_API_KEY`, and
  `music_store_chat` (URL and model) in `lab.auto.tfvars`.
- The ESO addon on the cluster `music-store`: `AddonInstall`
  `external-secrets` in `gitops/music-store` and the cluster label
  `addons.kubernetes.vmware.com/external-secrets: enabled`.
- `gitops/music-store-platform`, with the `ClusterSecretStore`
  `secret-store`, and its Application `music-store-platform`.
- `ExternalSecret`s `store-db` and `metal-oracle-model` in
  `gitops/music-store-dev/app`.

To roll out: add the two GitHub secrets, with a new database password
(the old one is in git history) and the current chat API key, then apply
the platform engineer Terraform. The next sync of `music-store` sets the
new password on the database, and the shop cannot reach the catalog
until ESO has written `store-db`. When ESO is running, delete the
hand-made Secrets `store-db` and `metal-oracle-model` in namespace
`music-store` of the cluster so that ESO can create its own, then restart
the storefront and chat Deployments.

### Removed

- The plain text password `music_password` from `catalog.yaml` and
  `app/music-store`.
- `gitops/music-store/app/backup/music-store-2026-10-22.json`, a live
  namespace snapshot with addresses.
- `store_password()` in `incident-demo/apply.py`, which nothing called,
  and the `store-db` and `metal-oracle-model` shapes from
  `incident-demo/secrets/templates.yaml`.

## 2026-10-26 (platform observability labels)

### Added

- The label `addons.kubernetes.vmware.com/platform-observability: enabled`
  on the clusters `music-store` (`gitops/music-store/cluster.yaml`),
  `agentminder` (`terraform/cloud-admin/org-config/agentminder.tf`) and
  `goad-store` (`incident/cluster/cluster.yaml`). The platform-observability
  Supervisor Service onboards labelled clusters to VCF Operations and
  installs the collectors. VKS already sets the helm-controller label the
  addon needs. `music-store` and `agentminder` were labelled by hand in
  the lab on 2026-10-26.

## 2026-10-20 (one-shot IAM blocks)

### Removed

- The `moved` and `removed` blocks in
  `terraform/cloud-admin/org-config/users.tf`. They were applied in the
  lab on 2026-10-20 (decision 36).

## 2026-10-20 (platform engineer group import)

### Added

- `terraform/cloud-admin/org-config/users.tf` imports the platform
  engineer group `ans-platform-engineer@set.lab` into the org
  (`terracurl_request.platform_engineer_group`, `POST
  /cloudapi/1.0.0/groups`, org role Organization User). It was added by
  hand before. TerraCurl's import only sets the ID, so the hand-made group
  was deleted and Terraform created it again, applied with `-target` on
  2026-10-20.

### Changed

- Platform engineers are the group, not users named one by one
  (decision 36). The group is admin of `default-project` and editor of
  `kro-authors`, through
  `kubectl_manifest.platform_engineer_group_project_role_binding`. The
  `kro-authors` binding moved there from `kro.tf` with a `moved` block.
- The Argo CD policy gives `role:admin` to `ans-platform-engineer@set.lab`
  instead of `william.arroyo@set.lab`.

### Removed

- The variable `platform_engineers`, the user imports, and the user role
  bindings in `default-project`. A `removed` block with `destroy = false`
  keeps the users in the org. The variable `kro_author_group` is now
  `platform_engineer_group`.

## 2026-10-20 (qwen endpoint name)

### Changed

- The ModelEndpoint `qwen` in `gitops/private-ai/pais.yaml` is now
  `qwen-14b-xlarge`: the model and the class are in the name. Neither can
  change on an existing endpoint, so a change to either one gives a new
  name, and Argo CD replaces the endpoint. `routingName` stays `qwen`.
  With `PruneLast=true`, the old endpoint is pruned only after the new one
  is Ready.
- PAIS allows two endpoints with the same `routingName`. The second
  one's InferenceGatewayRoute is `Routable: False`, reason `NameConflict`,
  and `qwen` keeps routing to the first. Tested 2026-10-20 in
  `private-ai`.
- The live `qwen` was created by hand on 2026-10-17 and has no Argo CD
  tracking-id, so Argo CD does not prune it. Delete it by hand once
  `qwen-14b-xlarge` is Ready.

## 2026-10-20 (live fixes from the agentic branch)

### Changed

These three changes were live from the branch `cursor/goad-agentic-5061`:
someone pointed the Applications `music-store` and `private-ai` at that
branch on the Supervisor, and it was not changed in git or Terraform. They
are now in git, so both Applications can follow `main` again.

- `gitops/music-store/catalog.yaml`: `catalog-init` grants `music_user`
  `USAGE, CREATE` on schema `public` and makes it the owner of the
  `albums` and `orders` tables and their sequences. On PostgreSQL 15 and
  later, `public` no longer grants CREATE by default, and `pgadmin` owned
  the tables.
- `gitops/music-store/cluster.yaml`: the workers are `best-effort-large`.
  The control plane stays `best-effort-medium`.
- `gitops/private-ai/pais.yaml`: the ModelEndpoint `qwen` serves Qwen 2.5
  Instruct 14B (Q4_K_M) on `best-effort-xlarge`, with 1Gi shared memory.
  The class cannot change on an existing endpoint, so moving from the 1.5B
  model means deleting the ModelEndpoint `qwen` and letting Argo CD create
  it again.

## 2026-10-19 (kro author project)

### Added

- The project `kro-authors`, in `terraform/cloud-admin/org-config/kro.tf`.
  The VCF SSO group `kro_author_group` (`ans-platform-engineer@set.lab`)
  has the project role `edit` in it, through a ProjectRoleBinding. The
  group must already be in the org.
- A small Supervisor Namespace `kro-authors-xxxxx` in that project, only so
  authors have a kubectl context.
- The outputs `kro_authors_project` and `kro_authors_namespace`.
- The goad org is listed in the multitenancy values of the kro Supervisor
  Service, with the project's uid. The vSphere admin sets this on the
  Supervisor, outside this repo.
- It needs a cloud admin apply of `org-config`. In the lab it was applied
  with `-target` for these resources only. The plan also shows an
  in-place change to the `machine_deployments` of
  `vcfa_vks_cluster.agentminder`. It is older drift of the containerd
  volumes override, and it was not applied. Decision 35 says why.

## 2026-10-16 (music store developer)

### Added

- The developer's part of the music store, in `gitops/music-store-dev/`.
  Two Applications, created by `terraform/platform-engineer/gitops.tf`:
  `music-store-dev-vm` syncs `users-vm/` into the `music-store`
  Supervisor Namespace, and `music-store-dev-app` syncs `app/` into the
  namespace `music-store` of the VKS cluster. Both retry (limit 10, 1m
  backoff, factor 2, maximum 10m), because they depend on the platform
  engineer's cluster and catalog.
- The Job `shop-endpoints` in `gitops/music-store-dev/users-vm/`. It
  writes the Endpoints `users-service` and `postgres-service` into the
  VKS cluster, from the users VM's load balancer address and the catalog's
  address. No address is in git.
- A ManagedEntity `music-store-cluster` in
  `terraform/platform-engineer/gitops.tf`, which registers the VKS cluster
  with Argo CD. It needs a platform engineer apply: the plan shows 3 to
  add, 0 to change, 0 to destroy.
- Decision 34 says why.

### Changed

- The users VM moved from `gitops/music-store/` to
  `gitops/music-store-dev/users-vm/`. The Application `music-store` now
  holds the VKS cluster and the catalog only.
- `app/music-store/kustomization.yml` lists the store, cart, orders, and
  traffic generator. The container database, container users, and chat
  are not listed. The script deploys chat to Tanzu with `cf push`.
- On merge, the Application `music-store` (`prune=true`) deletes the
  users VM, its VirtualMachineService `users-service`, and the Secret
  `music-users-bootstrap`. `music-store-dev-vm` makes them again after
  the platform engineer apply. The store was not in use yet, so the
  rebuild was accepted. Decision 34 says what a store in use would need.

## 2026-10-15 (AgentMinder CPU requests)

### Changed

- The `ssp` services of AgentMinder ask for 100m CPU each, not the chart's
  400m (1000m for `iarisk`), in `terraform/cloud-admin/agentminder`. With
  the chart's requests, `aigateway` and `iarisk` stayed Pending on two
  workers: "Insufficient cpu". The limits are unchanged. Decision 30 says
  why.

## 2026-10-15 (music store cluster)

### Added

- The music store's VKS cluster `music-store`, in
  `gitops/music-store/cluster.yaml`. Argo CD syncs it with the Application
  `music-store`. One control plane and two workers, Kubernetes
  v1.36.2+vmware.2. The containers in `app/music-store` are not deployed
  onto it by this Application. The 2026-10-16 entry does that.
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

### Documents

- `docs/decisions.md`: decisions 32 (the cluster is gitops) and 33 (the
  org's VM image).

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
- `docs/decisions.md`: decisions 29, 30, and 31.

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
