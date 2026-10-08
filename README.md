# The Grandmother of All Demos (GOAD)

This repository is the master for the GOAD demo. Manifests and the
walkthrough live here. A lab git server pulls a replica from this
remote.

The demo shows VMware Cloud Foundation across an application's life,
through four personas. Two of them are built so far: the cloud admin
and the platform engineer.

| Persona | Tool | What it builds | Where |
|---|---|---|---|
| Cloud admin | Terraform | The org: quota, networking, Avi load balancer, DSM policy | [terraform/cloud-admin](terraform/cloud-admin) |
| Platform engineer | Terraform | Service Engine Group, Supervisor Namespaces, Argo CD, and the handoff to it | [terraform/platform-engineer](terraform/platform-engineer) |
| Platform engineer | Argo CD | A DSM PostgreSQL database, Private AI Services, and the Qwen model | [gitops/private-ai](gitops/private-ai) |
| Platform engineer | Argo CD | The shop's users VM and its DSM catalog database | [gitops/music-store](gitops/music-store) |

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

Two files hold the inputs:

- `lab.auto.tfvars`, in git: everything about the lab that is not
  secret. The region, the Distributed VLAN Connection, the zone and its
  limits, VM classes, storage, and the DSM infrastructure policy. For a
  different lab, change this file and commit it.
- `terraform.tfvars`, not in git: `vcfa_password`, the provider
  administrator's password, and `org_admin_password`, which Terraform
  sets for the user `platform-admin`. If the demo is already built, copy
  the team's file.

```sh
cp backend.hcl.example backend.hcl             # then fill in: see "Terraform state"
terraform init -backend-config=backend.hcl
terraform apply
```

It creates the org `goad`, its administrator, quota, networking, the Avi
setting, and the DSM policy. If the last line of the plan warns that
regional networking is not realized, wait a minute and run
`terraform plan` until the warning is gone.

### 2. Give Argo CD read access to this repository

A read-only deploy key.

**If the demo is already built, do not do this step.** The key exists and
the team shares it. Get the file
`terraform/platform-engineer/.secrets/gitops-deploy-key` from a
teammate. A new key of your own would replace the one Argo CD uses, and
Argo CD would stop reading git.

Only for a first build, once, from the repository root:

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

Again two files:

- `lab.auto.tfvars`, in git: the region, zone, VPC, storage class, and
  the path of the deploy key.
- `terraform.tfvars`, not in git: `vcfa_password`, which is the
  `org_admin_password` from step 1, and `pais_admin_password_hash`, the
  output of `openssl passwd -6` for the Private AI Services user
  `admin`. If the demo is already built, copy the team's file.

```sh
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform apply
```

It creates the Service Engine Group, the namespaces `platform-xxxxx`,
`private-ai-xxxxx`, and `music-store-xxxxx`, and the Argo CD instance.
For each namespace other than `platform` it creates one Argo CD
Application that syncs `gitops/<namespace key>/` into it.

`terraform output namespaces` prints the generated namespace names.

### 4. Argo CD: database, Private AI Services, model, and the shop

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

Argo CD syncs `gitops/music-store/` the same way, into the `music-store`
namespace: the catalog database and the users VM, with the same kind of
Service name in front of the database.

### 5. Check it

- **VCF Automation**, as `platform-admin` in the org `goad`: three
  namespaces in the default project.
- **Argo CD**: the address is the `externalIP` in the status of the
  `ArgoCD` object in the `platform` namespace. Log in with "VCF
  Automation" as `platform-admin`. The Application `private-ai` is
  `Synced` and `Healthy`. On a first deploy the page answers only after
  Avi has started its Service Engines.
- **Private AI Services**: the address is the external IP of the Service
  `pais-ingress-default` in the `private-ai` namespace. Log in as
  `admin`. The model `qwen` is listed and ready.
- **Terraform**: `terraform plan` in each root shows no changes.

### Tear down

Reverse order. The platform engineer first, because the org cannot be
deleted while it has namespaces and a Service Engine Group.

```sh
cd terraform/platform-engineer && terraform destroy
cd ../cloud-admin && terraform destroy
```

Deleting a namespace deletes what Argo CD put in it: for `private-ai`,
the database, Private AI Services, and the model.

## Terraform state

State is remote, in the Terraform state registry of the lab's Gitea
server, under the organization `the-goad`. Terraform's `http` backend
talks to it, with locking. Gitea keeps every version of the state.

| Root | State name |
|---|---|
| `terraform/cloud-admin` | `goad-cloud-admin` |
| `terraform/platform-engineer` | `goad-platform-engineer` |

`backend.tf` in each root is empty on purpose. The address and the
shared token are in `backend.hcl`, which git ignores. A token cannot be
a Terraform variable: the backend is read before any variable is.

To set up a machine, in each root: copy `backend.hcl.example` to
`backend.hcl`, fill in the Gitea host, the owner `the-goad`, and the
token of the shared Gitea user `goad-terraform`, then run
`terraform init -backend-config=backend.hcl`. Get the token from a
teammate, never through git or email.

The state holds passwords and a private key. Anyone with that token can
read them.

[docs/terraform-state.md](docs/terraform-state.md) has the full setup,
what to do when it goes wrong, and how to go back to an earlier state.

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
`music-store` was added that way.
Manifests under `gitops/` do not set a namespace.

## Things to know

- **Lab values are in git, secrets are not.** `lab.auto.tfvars` in each
  root is committed, so everyone applies with the same lab values.
  `terraform.tfvars`, `backend.hcl`, and `.secrets/` are ignored by git.
- **The secret files are shared, not personal.** State is shared, so
  everyone must apply with the same passwords, the same deploy key, and
  the same password hash. Copy them from a teammate; do not make your
  own. With different values, each apply undoes the last person's.
  [docs/terraform-state.md](docs/terraform-state.md) lists what breaks.
- **The lab is shared.** `terraform apply` and `terraform destroy` in
  `cloud-admin` create and delete a real org.
- **No GPU.** The model runs on CPU. Do not say GPU on camera until one
  is allocated.
- **This repository is tied to one lab.** `lab.auto.tfvars` and the
  manifests in `gitops/` name this lab's region, storage policy, and DSM
  infrastructure policy.
- **The lab pulls one public image.** The Job in `gitops/private-ai/`
  uses `alpine/k8s` from Docker Hub.

## Documents

| Document | What it is |
|---|---|
| [docs/master-design-v5.md](docs/master-design-v5.md) | Design V5, transcribed from the current plan |
| [docs/walkthrough-script.md](docs/walkthrough-script.md) | The five-video script, including the unfinished beats |
| [docs/execution-plan.md](docs/execution-plan.md) | Suggested order of work |
| [docs/decisions.md](docs/decisions.md) | Choices made while building, and why |
| [docs/terraform-state.md](docs/terraform-state.md) | Where Terraform state is, and how to set up a machine for it |
| [CHANGELOG.md](CHANGELOG.md) | What changed, newest first |
| [terraform/cloud-admin/README.md](terraform/cloud-admin/README.md) | The cloud admin Terraform in detail |
| [terraform/platform-engineer/README.md](terraform/platform-engineer/README.md) | The platform engineer Terraform in detail |
