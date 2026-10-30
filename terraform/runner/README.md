# The self-hosted runner

The workflows in [.github/workflows](../../.github/workflows) run on
this runner. GitHub's own runners cannot reach VCF Automation or the lab's
Gitea server. The root [README](../../README.md) says how to start a
workflow.

It is [supervisor-github-runner](https://github.com/warroyo/supervisor-github-runner):
a Deployment of vSphere Pods that registers to the GitHub organization
`modern-apps-5` with the labels `self-hosted` and `lab`.

This root is not a persona and not part of the demo. It is applied by
hand, from a machine, once. No workflow runs it, because it builds what
the workflows run on. [Decision 25](../../docs/decisions.md) has the
reasons.

## What it creates

| Resource | What it is |
|---|---|
| `vsphere_namespace.runner` | The Supervisor Namespace `goad-runner`, made in vCenter, not through VCF Automation |
| `kubectl_manifest.github_app` | The Secret `github-app`: the GitHub App's ID and private key |
| `kubectl_manifest.runner_settings` | The ConfigMap `github-runner`: the organization and the labels |
| `kubectl_manifest.runner_entrypoint` | The ConfigMap with the scripts the two containers start with |
| `kubectl_manifest.runner_deployment` | The Deployment `github-runner`, two replicas |

The Deployment and the scripts are not in this repository. Terraform reads
them from supervisor-github-runner at the commit `runner_commit`, and
changes three things: the number of replicas, the runner container's CPU
and memory, and an annotation that restarts the pods when a script or the
settings change.

Each pod has two containers. `minter` holds the GitHub App's key and mints
one just-in-time runner registration at a time. `runner` takes each one,
runs one job, cleans up, and waits for the next. The runner container never
exits, so the next job starts within seconds. Before, it exited after every
job, and Kubernetes waited up to five minutes before restarting it.

The namespace has one storage policy and the Supervisor's workload
network, which is the default. It has no VM classes and no limits. It has
no project and no `-xxxxx` suffix, and VCF Automation does not list it.

Until `github_app_id` is set, Terraform creates the namespace and nothing
else.

## Logins

This root logs in to vCenter. For the Supervisor it uses the same login:
on every run it asks the Supervisor for a new session token. An expired
`vcf` session on your machine does not matter here, and `kubectl` does not
need to be logged in.

## Build it

Once for the lab. If `terraform plan` here shows no changes and
`terraform output runner_enabled` is `true`, it is built: do none of this.

You need `terraform` 1.11 or later, `gh`, the vCenter password, the state
token, and to be an owner of the GitHub organization.

### 1. The namespace

```sh
cd terraform/runner
cp terraform.tfvars.example terraform.tfvars   # then put the vCenter password in it
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform apply
```

The plan is one resource, the namespace.

### 2. The GitHub App

GitHub has no API that creates an App. A person confirms it in a browser.

From the repository root:

```sh
scripts/create-github-app.py
```

Open `http://localhost:8765/` in a browser on the same machine. From
another machine, first run `ssh -L 8765:localhost:8765 <that machine>`.

1. GitHub shows the App `goad-supervisor-runner`. Click **Create GitHub
   App**.
2. GitHub then shows the install page. Choose `modern-apps-5` and click
   **Install**.

The App is private, has no webhook, and has one permission: Self-hosted
runners, read and write, for the organization.

The script prints the App's ID, and writes the private key to
`terraform/runner/.secrets/private-key.pem`. Git ignores `.secrets/`.

### 3. The runner

Put the App's ID in `lab.auto.tfvars`, as `github_app_id`, and commit it.
The ID is not a secret. Then:

```sh
terraform apply
```

The plan is four resources. The apply waits until both pods are ready.
To see them register:

```sh
kubectl -n goad-runner logs deploy/github-runner -c minter
kubectl -n goad-runner logs deploy/github-runner -c runner
```

The minter prints `Minted runner`, and the runner `Listening for Jobs`. In GitHub,
the organization's Settings, Actions, Runners lists two runners with the
labels `self-hosted` and `lab`.

A `404` on `/installation` means that the App is not installed on the
organization: do the install in step 2. A `403` on `generate-jitconfig`
means that the App does not have the permission.

### 4. The workflows' secrets

The workflows read these repository secrets. Most are the team's shared
values, not new ones: see [docs/terraform-state.md](../../docs/terraform-state.md).

| Secret | Where the value is | Read by |
|---|---|---|
| `GITEA_STATE_TOKEN` | `password` in any `backend.hcl` | `cloud-admin`, `platform-engineer` |
| `VCFA_ADMIN_PASSWORD` | `vcfa_password` in `terraform/cloud-admin/org/terraform.tfvars` | `cloud-admin` |
| `CLOUD_ADMIN_PASSWORD` | `cloud_admin_password` in `terraform/cloud-admin/org/terraform.tfvars` | `cloud-admin` |
| `OPS_ADMIN_PASSWORD` | `ops_password` in `terraform/cloud-admin/org/terraform.tfvars` | `cloud-admin` |
| `HARBOR_ADMIN_PASSWORD` | `harbor_admin_password` in `terraform/cloud-admin/org/terraform.tfvars` | `cloud-admin` |
| `BROADCOM_REGISTRY_USERNAME`, `BROADCOM_REGISTRY_TOKEN` | `broadcom_registry_username` and `broadcom_registry_token` in `terraform/cloud-admin/org/terraform.tfvars` | `cloud-admin` |
| `MUSIC_STORE_HARBOR_ROBOT_SECRET` | `music_store_robot_secret` in `terraform/cloud-admin/org/terraform.tfvars` and `terraform/platform-engineer/terraform.tfvars` | `cloud-admin` sets it on the Harbor robot account `robot$music-store+builder`; `platform-engineer` writes it into the KV the image builds push with |
| `MUSIC_STORE_BUILD_KUBECONFIG` | Only in GitHub: `scripts/music-store-build-kubeconfig.sh` makes it from the ServiceAccount `pipeline-starter` | `music-store-images` |
| `SSP_REGISTRY_USERNAME`, `SSP_REGISTRY_PASSWORD` | `ssp_registry_username` and `ssp_registry_password` in `terraform/cloud-admin/agentminder/terraform.tfvars` | `cloud-admin` |
| `PLATFORM_ENGINEER_VCFA_TOKEN` | `vcfa_api_token` in `terraform/platform-engineer/terraform.tfvars` | `platform-engineer` |
| `PAIS_ADMIN_PASSWORD_HASH` | `pais_admin_password_hash` in `terraform/platform-engineer/terraform.tfvars` | `platform-engineer` |
| `GITOPS_DEPLOY_KEY` | The file `terraform/platform-engineer/.secrets/gitops-deploy-key` | `platform-engineer` |
| `MUSIC_STORE_DB_PASSWORD`, `MUSIC_STORE_CHAT_API_KEY` | `music_store_db_password` and `music_store_chat_api_key` in `terraform/platform-engineer/terraform.tfvars` | `platform-engineer` |
| `INCIDENT_GRAFANA_ADMIN_PASSWORD`, `INCIDENT_ZAMMAD_DB_PASSWORD`, `INCIDENT_ZAMMAD_ADMIN_PASSWORD` | The `incident_*` passwords in `terraform/platform-engineer/terraform.tfvars` | `platform-engineer`; `tanzu-apps` reads the Grafana one too |
| `INCIDENT_QWEN_API_KEY`, `INCIDENT_K8S_TOKEN`, `INCIDENT_SIDECAR_TOKEN` | `incident_qwen_api_key`, `incident_k8s_token` and `incident_sidecar_token` in `terraform/platform-engineer/terraform.tfvars` | `platform-engineer`, `tanzu-apps` |
| `INCIDENT_ZAMMAD_TOKEN`, `INCIDENT_AVI_USERNAME`, `INCIDENT_AVI_PASSWORD`, `INCIDENT_MCP_READ_TOKEN`, `INCIDENT_MCP_WRITE_TOKEN` | Only in GitHub: see [the incident apps' README](../../tanzu/metal-music-app-agentic-system/README.md) | `tanzu-apps` |
| `TANZU_HUB_CLIENT_ID`, `TANZU_HUB_CLIENT_ASSERTION` | The Tanzu Hub login of `goad-deployer` | all three, through the `cf-login` and `cf-token` actions |

Set each one with `gh secret set <name> --repo modern-apps-5/the-goad`.
For the deploy key, add `< terraform/platform-engineer/.secrets/gitops-deploy-key`.

## Joining, when it is already built

The same as the other roots. Get from a teammate: this root's
`terraform.tfvars`, the file `.secrets/private-key.pem`, and the state
token. Then `terraform init -backend-config=backend.hcl` and
`terraform plan`, which must show no changes.

## Change it

A plan that changes `kubectl_manifest.runner_deployment` restarts the
pods. A restart stops a running job: a `terraform apply` stopped in the
middle leaves a state lock that nobody holds. Before you apply such a
plan, check that no job is running:

```sh
kubectl -n goad-runner logs deploy/github-runner -c runner --tail=5
```

`Listening for Jobs` is safe. `Running job` is not.

| To change | Change |
|---|---|
| The runner image, or the scripts | `runner_commit` in `lab.auto.tfvars`, to a newer commit of supervisor-github-runner |
| How many jobs run at once | `runner_replicas` |
| The labels | `runner_labels`, and `runs-on` in every workflow |
| The disk a job has | In supervisor-github-runner, then `runner_commit` |

## Remove it

```sh
terraform destroy
```

Then delete the App in the organization's settings, under GitHub Apps.

## Things to know

- **`vsphere_namespace` cannot be imported.** A namespace of this name
  that Terraform did not create must be deleted first.
- **The state holds the App's private key and a Supervisor session
  token.** The token lasts hours. The key lasts until it is deleted in
  the App's settings.
- **A job has 4 GB of disk, and it is not kept.** A vSphere Pod gets
  about 250 MB unless it asks for more. The providers of the platform
  engineer root are 320 MB, so `terraform init` failed with `no space
  left on device`. supervisor-github-runner now asks for 4 GB, and
  `runner_commit` is a commit that has that. The disk is the pod's own,
  made and deleted with it: there is no volume claim, and nothing is
  left behind.
- **Terraform reads two files from GitHub on every plan.** Without a path
  to `raw.githubusercontent.com`, the plan fails.
