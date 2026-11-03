# Build GOAD

For a first build: from an empty org to the shop and the incident demo.
Most of the time is waiting for VKS clusters and the model.

## Before you start

The lab must already have:

- VCF Automation 9.1, with a region backed by a Supervisor.
- A Distributed VLAN Connection for the region, and a virtual network
  appliance cluster.
- Avi as the region's load balancer, in tenant managed mode.
- Data Services Manager (DSM) activated for the region, with an
  infrastructure policy and PostgreSQL 16 enabled.
- Private AI Services installed as a Supervisor Service, with the Qwen
  model and the engine image in the Supervisor's Harbor.
- A public proxy cache project, `tanzu-platform-content`, in the
  Supervisor's Harbor, for Broadcom's Tanzu Platform content registry
  and its Bitnami images.
- A public Harbor project, `music-store`, for the music store's images,
  and a robot account the platform engineer pushes them with.
- The Argo CD Supervisor Service, and Secret Store (the vault injector) on
  the Supervisor.
- The VKS addons `external-secrets` and `cert-manager` in the Supervisor's
  addon repository.
- Avi's `System-WAF-Policy`, set to enforcement if the shop's WAF must
  block.
- A Tanzu Platform foundation with its runtime on a VKS cluster, the org
  `Goad`, and the Tanzu Hub account `goad-deployer` that the workflows
  log in as. The incident apps run there: a `cf push` places them on the
  runtime's VKS cluster.
- NSX with vDefend, for the security admin's guardrails, and VCF
  Operations, for the cloud admin's dashboards and for VCF SSO.
- An Active Directory in VCF SSO, with a group for the platform engineers
  and a service account for the platform engineer's automation.
- A Terraform state backend. GOAD uses a Gitea server's Terraform state
  registry: see [terraform-state.md](terraform-state.md).
- A self-hosted GitHub runner in the lab, only to run the workflows:
  see [terraform/runner/README.md](../terraform/runner/README.md).

Every name and address of the lab is in git. Before the first build in
another lab, change them: see [adapt-to-your-lab.md](adapt-to-your-lab.md).

Your machine needs `terraform` 1.11 or later, `git`, `gh`, `openssl`, `curl`, `jq`, and
a network path to VCF Automation, to Tanzu Platform, and to the lab's Gitea server.

You need the password of the provider administrator (`admin` in the
`System` org), admin rights on this GitHub repository, and the token of
the Gitea user that holds the Terraform state: see [terraform-state.md](terraform-state.md).

## 1. Cloud admin: create the org

```sh
cd terraform/cloud-admin/org
cp terraform.tfvars.example terraform.tfvars
```

Two files hold the inputs:

- `lab.auto.tfvars`, in git: everything about the lab that is not
  secret. The region, the Distributed VLAN Connection, the zone and its
  limits, VM classes, storage, the DSM infrastructure policy, and the
  Harbor address. For a
  different lab, change this file and commit it.
- `terraform.tfvars`, not in git: `vcfa_password`, the provider
  administrator's password, `cloud_admin_password`, which Terraform sets
  for the org's one local user `cloud-admin`, `ops_password`, the
  VCF Operations administrator's password, `harbor_admin_password`, the
  Supervisor's Harbor administrator's password, and
  `broadcom_registry_username` and `broadcom_registry_token`, the
  Broadcom registry login of the Harbor proxy cache, and
  `music_store_robot_secret`, the secret of the music store's Harbor
  robot account. If the demo is already built,
  copy the team's file.

```sh
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform apply
```

It creates the org `goad`, its local user `cloud-admin` (Organization
Administrator), VCF SSO for the org, quota, networking, the Avi setting,
and the DSM policy. If the last line of the plan warns that regional
networking is not realized, wait a minute and run `terraform plan` until
the warning is gone.

The VCF SSO part makes the org's OIDC client in the VCF Identity Broker
through VCF Operations' internal API, which is unsupported and can change
in another release. See [decision 27](decisions.md).

## 1b. Cloud admin: configure the org

```sh
cd ../org-config
cp terraform.tfvars.example terraform.tfvars   # cloud_admin_password, the same as in org
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform apply
```

It logs in to the org as `cloud-admin` and imports from VCF SSO the AD
group `ans-platform-engineer@set.lab`, whose members become admins of the
project `default-project`, and the AD service account
`svc.platform_engineer@set.lab`. It also creates the Service Engine
Group, the project `kro-authors` for kro APIs, the project `cloud-admin`,
a namespace in it, and the VKS cluster `agentminder`. The cluster takes a
while to come up.

## 1c. Cloud admin: install AgentMinder

```sh
cd ../agentminder
cp terraform.tfvars.example terraform.tfvars   # cloud_admin_password and the registry login
cp backend.hcl.example backend.hcl             # then put the state token in it
export TF_HTTP_PASSWORD=<the same token>       # the remote state read cannot use backend.hcl
terraform init -backend-config=backend.hcl
terraform apply
```

It reads the cluster from the state of `org-config` and installs
`ingress-nginx` and AgentMinder with Helm. AgentMinder is installed
small: [decision 30](decisions.md). Its agents are registered later,
in step 6. Avi DNS makes the record for
`agentminder.goad.gpu.set.lab` by itself: see decision 31.

## 1d. Cloud admin: VCF Operations content

This root needs nothing from the others, and they need nothing from it.
Apply it at any time.

```sh
cd terraform/cloud-admin/ops
cp terraform.tfvars.example terraform.tfvars   # ops_password
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform apply
```

It imports the platform observability dashboards in `dashboards/` and
turns on the alert for VKS node disk latency. See
[its README](../terraform/cloud-admin/ops/README.md).

## 2. Give Argo CD read access to this repository

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

## 3. Platform engineer: namespaces, Argo CD, handoff

Make the API token first, once, by hand: log in to the org `goad` with
VCF SSO as `svc.platform_engineer@set.lab`, then User Preferences, API
Tokens. A new AD user can log in only after the Identity Broker syncs the
directory (VCF Operations, Fleet Management, Identity & Access, VCF SSO).
If the demo is already built, the team's `terraform.tfvars` has the token.

```sh
cd terraform/platform-engineer
cp terraform.tfvars.example terraform.tfvars
```

Again two files:

- `lab.auto.tfvars`, in git: the region, zone, VPC, storage class, and
  the path of the deploy key.
- `terraform.tfvars`, not in git: `vcfa_api_token`, the API token above;
  `pais_admin_password_hash`, the output of `openssl passwd -6` for the
  Private AI Services user `admin`; the music store's and the platform
  tools' passwords and keys, which Terraform writes to Secret Store; and
  the incident apps' keys for their Cloud Foundry services. In GitHub
  each is a repository secret: `terraform.tfvars.example` names them. If
  the demo is already built, copy the team's file.

```sh
cp backend.hcl.example backend.hcl
export CF_ACCESS_TOKEN=<a Tanzu Platform token for goad-deployer>
terraform init -backend-config=backend.hcl
terraform apply
```

It creates the namespaces `platform-xxxxx`, `private-ai-xxxxx`,
`music-store-xxxxx`, and `platform-tools-xxxxx`, and the Argo CD
instance. For each namespace other than `platform` it creates one Argo CD
Application that syncs `gitops/<namespace key>/` into it. It registers
the VKS clusters `music-store` and `platform-tools` with Argo CD and
creates the Applications that sync into them. It writes the secrets into
Secret Store as `KeyValueSecret`s (decision 38). It also creates the
content library `goad-images` and uploads the Ubuntu image to it, for
the users VM. The first apply downloads about 570 MiB with `curl`, so the
machine needs internet access to cloud-images.ubuntu.com.

On Tanzu Platform it creates the space `metal-music-app-agentic-system`
in org `Goad`, and the user-provided services `goad-qwen` and `sc-*` that
the incident apps bind (decision 40).

`terraform output namespaces` prints the generated namespace names.

## 4. Argo CD: database, Private AI Services, model, and the shop

Nothing to run. Argo CD syncs `gitops/private-ai/` from `main` in waves
and waits for each to be healthy:

| Wave | Resource | Typical time |
|---|---|---|
| 0 | DSM `PostgresCluster` `pais-db`, and its Service | 5 minutes |
| 1 | The Job that points the Service at the database | under a minute |
| 2 | `PAISConfiguration` | 3 minutes |
| 3 | `ModelEndpoint` `qwen-14b-xlarge`, routing name `qwen` | a few minutes, for the model load |

DSM assigns the database its address when it creates it. Nothing in git
holds that address: Private AI Services connects to the Service name
`pais-db`, and the Job in wave 1 writes the address into the Service's
Endpoints.

Argo CD syncs `gitops/music-store/` the same way, into the `music-store`
namespace: the catalog database and the VKS cluster `music-store` with its
ESO and cert-manager addons, with the same kind of Service name in front
of the database. The cluster takes about 15 minutes to build. Then
`music-store-platform` puts the `ClusterSecretStore` and the Gateway's
certificate in the cluster.

The same Application creates the users VM in that namespace, in wave 0.
In wave 3, after the catalog is filled and the cluster is healthy, a Job
writes the VM's address and the catalog's address into Endpoints in the
VKS cluster. Argo CD then syncs `gitops/music-store-apps/` as the
platform engineer. The Application `music-store-apps` deploys the
containers onto the cluster. It depends on the cluster and the catalog,
so it retries until those exist. The developer writes only the code in
`apps/music-store/`.

Argo CD syncs `gitops/platform-tools/` into the `platform-tools`
namespace: the VKS cluster `platform-tools` and its ESO addon. Then
`platform-tools-apps` puts Zammad, Grafana, Prometheus and the blackbox
exporter in it, in namespace `incident-tools`. `platform-tools/` also
installs the Tekton addon. The Application `platform-tools-builds` syncs
`gitops/platform-tools-builds/` into the namespace `music-store-builds`
of that cluster: the pipeline that builds the music store's images from
`apps/music-store/`, with the Dockerfile template the platform engineer
owns. The workflow `music-store-images.yml` starts a PipelineRun and
opens a pull request with the new image tags
(`depot.kube-system.svc/music-store/<service>:<commit>`, decision 48).

## 5. Security admin: vDefend guardrails

Needs the cluster `music-store` up, with Antrea's NSX integration, from
step 4.

```sh
cd terraform/security-admin
cp terraform.tfvars.example terraform.tfvars   # nsx_password
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform apply
```

It writes the music store's vDefend rules in NSX, and NSX pushes them into
the cluster as Antrea policies. See
[its README](../terraform/security-admin/README.md) and
[security-architecture.md](security-architecture.md).

## 6. Agentic ops engineer: register the incident agents in AgentMinder

Needs the space from step 3 and AgentMinder from the cloud admin. The cloud
admin copies AgentMinder's admin client into two values once: see
[the root's README](../terraform/agentic-ops/README.md).

```sh
cd terraform/agentic-ops
cp terraform.tfvars.example terraform.tfvars   # the admin client, and the sidecar token
cp backend.hcl.example backend.hcl             # then put the state token in it
export CF_ACCESS_TOKEN=<a Tanzu Platform token for goad-deployer>
terraform init -backend-config=backend.hcl
```

Then plan and apply as its [README](../terraform/agentic-ops/README.md) says,
without printing the plan: the plan can show client secrets. It creates
the MCP servers and clients in AgentMinder, the services `am-*` that hand
each diagnostic agent its client, and the `sc-*` services that give each
agent its tools.

## 7. Push the incident apps

Zammad starts empty. Create its admin and the walk tickets' organization,
then store the admin's API token as the GitHub secret
`INCIDENT_ZAMMAD_TOKEN`: see [gitops/README.md](../gitops/README.md). Then
run the `tanzu-apps` workflow, or push a change under
`tanzu/metal-music-app-agentic-system`.
[Its README](../tanzu/metal-music-app-agentic-system/README.md) lists the
GitHub secrets it reads and how to start a walk.

## 8. Check it

- **VCF Automation**, as a member of `ans-platform-engineer@set.lab`
  in the org `goad`: four
  namespaces in the default project.
- **Argo CD**: the address is the `externalIP` in the status of the
  `ArgoCD` object in the `platform` namespace. Log in with "VCF
  Automation" as the same user. The Application `private-ai` is
  `Synced` and `Healthy`. On a first deploy the page answers only after
  Avi has started its Service Engines.
- **Private AI Services**: the address is the external IP of the Service
  `pais-ingress-default` in the `private-ai` namespace. Log in as
  `admin`. The model `qwen` is listed and ready.
- **AgentMinder**: `kubectl -n ssp get pods` on the cluster
  `agentminder` shows every pod running. Then
  `https://agentminder.goad.gpu.set.lab` answers.
- **VKS clusters**: the Cluster `music-store` in the `music-store`
  namespace and the Cluster `platform-tools` in the `platform-tools`
  namespace are Available (`kubectl get clusters` in each namespace).
- **The shop**: `https://music.goad.gpu.set.lab` answers, with a
  self-signed certificate.
- **The incident tools**: `http://zammad.goad.gpu.set.lab` and
  `http://grafana.goad.gpu.set.lab` answer.
- **The incident apps**: `cf apps` in org `Goad`, space
  `metal-music-app-agentic-system`, shows nine apps running.
- **vDefend**: on the cluster `music-store`,
  `kubectl get acnp -l ccp-adapter.antrea.tanzu.vmware.com/managedBy=ccp-adapter`
  lists the pushed policy.
- **Terraform**: `terraform plan` in each root shows no changes.

## Tear down

Reverse order. `terraform/agentic-ops` first: it needs the running
AgentMinder to delete its objects, and its services are in the platform
engineer's space. Then `security-admin`, while the cluster it ties its
policy to still exists. Then the platform engineer, because its namespaces use
the Service Engine Group, and the org cannot be deleted while it has
namespaces and a Service Engine Group. Then `agentminder`, because its
cluster must exist for Helm to remove what it installed. Then
`org-config`, then `org`. `cloud-admin/ops` stands alone: destroy it
whenever you like.

```sh
cd terraform/agentic-ops && terraform destroy
cd ../security-admin && terraform destroy
cd ../platform-engineer && terraform destroy
cd ../cloud-admin/agentminder && terraform destroy
cd ../org-config && terraform destroy
cd ../org && terraform destroy
cd ../ops && terraform destroy
```

Deleting a namespace deletes what Argo CD put in it: for `private-ai`,
the database, Private AI Services, and the model; for `music-store` and
`platform-tools`, their VKS clusters.

## The secrets you make

The `terraform.tfvars` files and the GitHub repository secrets hold the
same values. [terraform/runner/README.md](../terraform/runner/README.md)
maps each GitHub secret to its `terraform.tfvars` value. On a first build,
this is where each value comes from.

| Value | Root | Where it comes from |
|---|---|---|
| `vcfa_password` | `cloud-admin/org` | The VCF Automation provider administrator's password. It exists already |
| `cloud_admin_password` | `cloud-admin/org`, `org-config`, `agentminder` | Choose one. Terraform sets it on the org's local user `cloud-admin`. The same value in all three |
| `ops_password` | `cloud-admin/org`, `cloud-admin/ops` | The VCF Operations administrator's password. It exists already |
| `harbor_admin_password` | `cloud-admin/org` | The Supervisor Harbor's administrator password, set by the Harbor Supervisor Service |
| `broadcom_registry_username`, `broadcom_registry_token` | `cloud-admin/org` | A Broadcom registry login for `tanzu-platform-content.packages.broadcom.com` |
| `music_store_robot_secret` | `cloud-admin/org`, `platform-engineer` | Choose one: 8 to 128 characters, with an upper case letter, a lower case letter and a digit. The same value in both |
| `ssp_registry_username`, `ssp_registry_password` | `cloud-admin/agentminder` | A Broadcom registry login for `securityservices.packages.broadcom.com` |
| Gitea token | every `backend.hcl` | The token of the Gitea user that owns the state: see [terraform-state.md](terraform-state.md) |
| Deploy key | `platform-engineer` | Step 2 |
| `vcfa_api_token` | `platform-engineer` | Step 3 |
| `pais_admin_password_hash` | `platform-engineer` | `openssl passwd -6` of a password you choose for the Private AI Services user `admin` |
| `music_store_db_password`, `incident_grafana_admin_password`, `incident_zammad_db_password`, `incident_zammad_admin_password` | `platform-engineer` | Choose each. Terraform writes them to Secret Store |
| `music_store_chat_api_key`, `incident_qwen_api_key` | `platform-engineer` | Private AI Services API keys for the model, after step 4 |
| `incident_k8s_token` | `platform-engineer` | The Secret `goad-k8s-mcp-token` in namespace `platform-tools` of the cluster `music-store`, after step 4 |
| `nsx_password` | `security-admin` | The password of `nsx_username` in NSX Manager. It exists already |
| `agentminder_client_id`, `agentminder_client_secret` | `agentic-ops` | The Secret `ssp-ssp-secret-defaulttenantclient` in namespace `ssp` of the cluster `agentminder`, after step 1c |
| `incident_sidecar_token` | `agentic-ops` | Choose one, random |

The values marked "after step 4" do not exist at step 3. Apply step 3
with a placeholder for each, then set the real value and apply again.

Some values are only GitHub secrets, never in a `terraform.tfvars`:

| GitHub secret | Where it comes from |
|---|---|
| `TANZU_HUB_CLIENT_ID`, `TANZU_HUB_CLIENT_ASSERTION` | The Tanzu Hub login of `goad-deployer` |
| `MUSIC_STORE_BUILD_KUBECONFIG` | `scripts/music-store-build-kubeconfig.sh`, after step 4 |
| `INCIDENT_ZAMMAD_TOKEN` | Zammad's admin API token, after step 4: see step 7 |
| `INCIDENT_AVI_USERNAME`, `INCIDENT_AVI_PASSWORD` | An Avi Controller login for the incident apps |
| `INCIDENT_MCP_READ_TOKEN`, `INCIDENT_MCP_WRITE_TOKEN` | Choose two different random values |

Generate a random value with `openssl rand -hex 32`. Keep each value in a
password manager.

## Joining a lab that is already built

If your team has already built GOAD, do not run these steps. Get the
team's shared files and set up your machine as
[terraform-state.md](terraform-state.md) says: every `terraform plan`
then shows no changes.

## Things to know

- **Lab values are in git, secrets are not.** `lab.auto.tfvars` in each
  root is committed, so everyone applies with the same lab values.
  `terraform.tfvars`, `backend.hcl`, and `.secrets/` are ignored by git.
- **The lab is shared.** `terraform apply` and `terraform destroy` in
  `cloud-admin/org` create and delete a real org.
- **No GPU.** The model runs on CPU.
- **This repository is tied to one lab.** `lab.auto.tfvars`,
  `backend.tf`, the manifests in `gitops/`, and the incident apps'
  manifest name this lab's addresses and policies.
  [adapt-to-your-lab.md](adapt-to-your-lab.md) lists each one.
- **AgentMinder needs a registry login.** Its images come from Broadcom's
  registry. `terraform/cloud-admin/agentminder` takes the login as
  `ssp_registry_username` and `ssp_registry_password`. Copy the team's
  `terraform.tfvars`.
- **The lab pulls public images.** The Jobs in `gitops/` use `alpine/k8s`
  and `postgres` from Docker Hub.
