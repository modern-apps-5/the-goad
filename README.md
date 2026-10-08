# The Grandmother of All Demos (GOAD)

This repository is the master for the GOAD demo. Manifests and the
walkthrough live here. A lab git server pulls a replica from this
remote.

The demo shows VMware Cloud Foundation across an application's life,
through four personas. Two of them are built so far.

| Persona | Tool | What it builds | Where |
|---|---|---|---|
| Cloud admin | Terraform | The org: quota, networking, Avi load balancer, DSM policy | [terraform/cloud-admin](terraform/cloud-admin) |
| Platform engineer | Terraform | Service Engine Group, Supervisor Namespaces, Argo CD, and the handoff to it | [terraform/platform-engineer](terraform/platform-engineer) |
| Platform engineer | Argo CD | A DSM PostgreSQL database, Private AI Services, and the Qwen model | [gitops/private-ai](gitops/private-ai) |

The music-store application is in [app/music-store](app/music-store) as
plain container manifests. Argo CD does not deploy those containers yet.

[gitops/music-store](gitops/music-store) is the users VM Service and the
DSM catalog. Neither file sets a namespace or an address. Terraform
creates the `music-store` namespace with the others, and Argo CD syncs
that directory into it. The shop login is `admin` / `admin`. The catalog
Service is `postgres-service`, which is the `DB_HOST` the containers
already use.

## Quickstart

From an empty org to a served model. About 20 minutes, most of it
waiting.

### Before you start

The lab must already have:

- VCF Automation 9.1, with a region backed by a Supervisor.
- A Distributed VLAN Connection for the region, and a virtual network
  appliance cluster.
- Avi as the region's load balancer, in tenant managed mode.
- Data Services Manager (DSM) activated for the region, with an
  infrastructure policy and PostgreSQL 16 enabled.
- Private AI Services installed as a Supervisor Service, with the Qwen
  model and the engine image in the Supervisor's Harbor.
- The Argo CD Supervisor Service.

Your machine needs `terraform` 1.11 or later, `git`, `gh`, `openssl`, and
a network path to VCF Automation.

You need the password of the provider administrator (`admin` in the
`System` org), and admin rights on this GitHub repository.

### 1. Cloud admin: create the org

```sh
cd terraform/cloud-admin
cp terraform.tfvars.example terraform.tfvars
```

Fill in `terraform.tfvars`:

| Variable | What to put |
|---|---|
| `vcfa_url`, `vcfa_password` | VCF Automation URL and the provider administrator's password |
| `org_admin_password` | A new password. Terraform creates the user `platform-admin` with it. |
| `region_name`, `distributed_vlan_connection_name`, `vna_cluster_name` | Names of the existing region, its connection, and its appliance cluster |
| `zone_allocations` | The zone name, with CPU and memory limits and a reservation |
| `vm_class_names`, `storage_policy_limits_mib` | VM classes and storage the org can use |
| `dsm_infrastructure_policy_names` | The DSM infrastructure policy for the org's databases |

```sh
terraform init
terraform apply
```

It creates the org `goad`, its administrator, quota, networking, the Avi
setting, and the DSM policy. If the last line of the plan warns that
regional networking is not realized, wait a minute and run
`terraform plan` until the warning is gone.

### 2. Give Argo CD read access to this repository

A read-only deploy key. Run this once, from the repository root:

```sh
mkdir -p terraform/platform-engineer/.secrets
ssh-keygen -t ed25519 -N '' -f terraform/platform-engineer/.secrets/gitops-deploy-key
gh repo deploy-key add terraform/platform-engineer/.secrets/gitops-deploy-key.pub \
  --repo modern-apps-5/the-goad --title goad-argocd-read
```

`.secrets/` is ignored by git. If GitHub answers "Deploy keys are
disabled for this repository", an organization owner must enable them in
the organization's settings.

### 3. Platform engineer: namespaces, Argo CD, handoff

```sh
cd terraform/platform-engineer
cp terraform.tfvars.example terraform.tfvars
```

Fill in `terraform.tfvars`:

| Variable | What to put |
|---|---|
| `vcfa_url` | Same as step 1 |
| `vcfa_password` | The `org_admin_password` from step 1 |
| `region_name`, `zone_name` | Same region and zone as step 1 |
| `vpc_name` | `default-<region_name>` |
| `storage_class_name` | The storage policy, by its Kubernetes name (lower case, hyphens) |
| `gitops_repo_ssh_key_file` | `.secrets/gitops-deploy-key` |
| `pais_admin_password_hash` | Output of `openssl passwd -6`, for the Private AI Services user `admin` |

```sh
terraform init
terraform apply
```

It creates the Service Engine Group, the namespaces `platform-xxxxx` and
`private-ai-xxxxx`, the Argo CD instance, and one Argo CD Application
that syncs `gitops/private-ai/` into the `private-ai` namespace.

`terraform output namespaces` prints the generated namespace names.

### 4. Argo CD: database, Private AI Services, model

Nothing to run. Argo CD syncs `gitops/private-ai/` from `main` in waves
and waits for each to be healthy:

| Wave | Resource | Typical time |
|---|---|---|
| 0 | DSM `PostgresCluster` `pais-db`, and its Service | 5 minutes |
| 1 | The Job that points the Service at the database | under a minute |
| 2 | `PAISConfiguration` | 3 minutes |
| 3 | `ModelEndpoint` `qwen` | 1 minute |

DSM assigns the database its address when it creates it. Nothing in git
holds that address: Private AI Services connects to the Service name
`pais-db`, and the Job in wave 1 writes the address into the Service's
Endpoints.

### 5. Check it

- **VCF Automation**, as `platform-admin` in the org `goad`: two
  namespaces in the default project.
- **Argo CD**: the address is the `externalIP` in the status of the
  `ArgoCD` object in the `platform` namespace. Log in with "VCF
  Automation" as `platform-admin`. The Application `private-ai` is
  `Synced` and `Healthy`. On a first deploy the page answers only after
  Avi has started its Service Engines.
- **Private AI Services**: the address is the external IP of the Service
  `pais-ingress-default` in the `private-ai` namespace. Log in as
  `admin`. The model `qwen` is listed and ready.

### Tear down

Reverse order. The platform engineer first, because the org cannot be
deleted while it has namespaces and a Service Engine Group.

```sh
cd terraform/platform-engineer && terraform destroy
cd ../cloud-admin && terraform destroy
```

Deleting the `private-ai` namespace deletes the database, Private AI
Services, and the model with it.

## Layout

```
terraform/cloud-admin/         Provider (System) org scope
terraform/platform-engineer/   Inside the org; stops at the handoff to Argo CD
  manifests/                   Manifests that Terraform applies
gitops/<namespace key>/        What Argo CD syncs into that namespace
app/music-store/               The application's container manifests
docs/                          Design, script, plan, decisions
```

One rule decides where a file goes: if Terraform applies it, it is under
`terraform/`. If Argo CD syncs it, it is under `gitops/`.

To give Argo CD another namespace, add it to `namespaces` in
`terraform/platform-engineer` and add the directory `gitops/<key>/`.
Manifests under `gitops/` do not set a namespace.

## Things to know

- **Secrets stay local.** `terraform.tfvars`, `.secrets/`, and Terraform
  state are ignored by git. State holds secrets. Choose a backend before
  a second person applies.
- **The lab is shared.** `terraform apply` and `terraform destroy` in
  `cloud-admin` create and delete a real org.
- **No GPU.** The model runs on CPU. Do not say GPU on camera until one
  is allocated.
- **Lab values are in `gitops/`.** The storage policy and the DSM
  infrastructure policy are this lab's.
- **The lab pulls one public image.** The Job in `gitops/private-ai/`
  uses `alpine/k8s` from Docker Hub.

## Documents

| Document | What it is |
|---|---|
| [docs/master-design-v5.md](docs/master-design-v5.md) | Design V5, transcribed from the current plan |
| [docs/walkthrough-script.md](docs/walkthrough-script.md) | The five-video script, including the unfinished beats |
| [docs/execution-plan.md](docs/execution-plan.md) | Suggested order of work |
| [docs/decisions.md](docs/decisions.md) | Choices made while building, and why |
| [CHANGELOG.md](CHANGELOG.md) | What changed, newest first |
| [terraform/cloud-admin/README.md](terraform/cloud-admin/README.md) | The cloud admin Terraform in detail |
| [terraform/platform-engineer/README.md](terraform/platform-engineer/README.md) | The platform engineer Terraform in detail |
