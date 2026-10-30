# Decisions

Choices made while building this repository, and why. Each one lists
what would make it worth a second look. Newest last.

Lab facts these rest on: VCF Automation 9.1.1, one region backed by one
Supervisor, a Distributed Transit Gateway with a Distributed VLAN
Connection for external traffic, Avi as the load balancer, and the
`vmware/vcfa` Terraform provider 1.2.3.

## 1. The cloud admin Terraform starts at the org

The region, its Distributed VLAN Connection, and the IP space already
exist in the lab. `terraform/cloud-admin/org` reads them and creates the org
and what belongs to it. See 26 for the second root.

Why: a Supervisor belongs to one region, and the lab is shared. Creating
a second region is not possible, and importing the existing one would
put shared infrastructure under this repository's `terraform destroy`.

Look again if: the demo gets a lab of its own.

## 2. Regional networking is created with TerraCurl

`vcfa_org_regional_networking` requires a provider gateway. This region
has none; it uses a Distributed VLAN Connection. TerraCurl calls
`/cloudapi/vcf/regionalNetworkingSettings` with the connection instead.

Two resources do it. The create call answers `202` with an empty body,
so a second resource reads the new setting and owns the delete.

Why: no other way to attach the org to this kind of region from
Terraform.

Look again if: the provider accepts a Distributed VLAN Connection.

## 3. Apply does not wait for regional networking to be realized

The setting was realized in 4 seconds twice and in 140 seconds once.
TerraCurl can retry on a status code only, and the list call answers
`200` in every state. Apply moves on, and a `check` block warns while the
status is not `REALIZED`.

Why: a fixed sleep long enough for the slow case makes every run slow,
and is still a guess.

Look again if: the next step fails often because it ran too soon.

## 4. The cloud admin logs in with user and password

An API token session cannot create users. VCF Automation answers
`ACCESS_TO_RESOURCE_IS_FORBIDDEN`, and `org.tf` creates the org's one
local user, `cloud-admin`.

Why: one credential that can do everything in the root.

Both cloud admin roots log in this way: `org` as the provider
administrator, `org-config` as `cloud-admin`. The platform engineer root
is different: see 28.

## 5. The DSM policy goes through VCF Automation, with `kubernetes_manifest`

A data service policy lives in DSM. VCF Automation proxies the region's
DSM API at `/proxy/external-endpoint/api/dsm/regions/<region>/` and
accepts the provider session token. That API is a full Kubernetes API
with OpenAPI, so `kubernetes_manifest` manages the policy.

Why: one endpoint and one certificate, no route to the DSM appliance,
and a real resource with drift detection. The first version called the
appliance directly with TerraCurl.

## 6. Avi is tenant managed

The cloud admin turns the load balancer on for the org with a Service
Engine quota and creates the org's Service Engine Group, in
`terraform/cloud-admin/org-config`. The platform engineer's namespaces
name the group.

Why: that is how the lab region already runs. A Supervisor Namespace
that names a group is refused until both exist. The platform engineer
used to create the group. It moved when the cloud admin got a namespace
of its own for AgentMinder (29): that namespace needs the group, and the
cloud admin runs first.

Cost: a one-shot `import` block in `org-config` and `removed` blocks in
`terraform/platform-engineer/namespace.tf` moved the existing group
between states without deleting it. They were applied once in the lab
and then deleted from the code.
Teardown has one more rule: destroy the platform engineer before
`org-config`, because its namespaces use the group.

## 7. Which provider applies a Kubernetes object

- `kubernetes_manifest` when the API publishes OpenAPI and its address
  is known at plan time. Only the DSM proxy qualifies.
- `kubectl_manifest` (`alekc/kubectl`) for everything else that is
  Kubernetes. The org API publishes no OpenAPI for its kinds, and
  `kubernetes_manifest` fails with "resource not found in OpenAPI
  index".
- TerraCurl only for calls that are not Kubernetes: regional networking,
  the Avi setting, the service account role.

For the platform namespace, the API address holds a generated ID and is
known only during apply. `lazy_load = true` on the `kubectl` provider
lets it plan. Without that option the provider fails at plan, which is
why an earlier version used TerraCurl there.

Why: prefer the tool that gives create, update, delete, and drift.

## 8. No `wait_for` on the Service Engine Group

`kubectl_manifest` waits with a watch. VCF Automation does not let an
organization administrator watch that kind, although create, get, and
delete are allowed. A 20-second sleep stands in. The group was
programmed within seconds.

## 9. The org's default project and VPC

VCF Automation creates `default-project` and the VPC `default-<region>`
with the org. The platform engineer uses them.

Why: the demo has one team and one application. A project and a VPC of
its own would be two more objects that show nothing.

Look again if: the demo needs to show tenancy inside the org.

## 10. Terraform manifests stay with Terraform

`gitops/` holds only what Argo CD syncs. A manifest that Terraform
applies, such as the Argo CD instance, lives in that Terraform root's
`manifests/`.

Why: Argo CD does not sync itself, and one rule for where a file goes is
easier than two.

## 11. Argo CD login uses VCF Automation

With a load balancer address, the Argo CD service registers the instance
with VCF Automation as an OIDC client on its own. The manifest sets no
`oidc` block. It sets `rbac`, because login without a policy can do
nothing.

Why: no client ID or secret to manage. The `oidc` block is for bringing
another identity provider.

## 12. Terraform gives the Argo CD service account its role

The service creates the instance's VCF Automation service account with
no role. Every namespace registration then fails with "No assigned
roles". The portal adds the role; the API does not. Terraform adds
"ArgoCD Instance" with TerraCurl.

## 13. The handoff is one registration and one Application per namespace

Namespace names are generated, so git cannot name them. For each
namespace other than `platform`, Terraform creates a `ManagedEntity` and
an `Application` that syncs `gitops/<key>/` into it.

Why: it is the smallest thing that works. No ApplicationSet, no labels
to join on, no application of applications.

Look again if: the number of namespaces or clusters makes one
Application each a burden.

## 14. Argo CD reads the repository with a deploy key

A read-only deploy key on this repository. The private half is in
`terraform/platform-engineer/.secrets/`, which git ignores, and Terraform
puts it in Argo CD's repository Secret.

Why: the key belongs to the repository, not to a person, and can read
nothing else. A personal token would stop working when its owner leaves
the organization.

Cost: the lab needs outbound SSH to GitHub.

Look again if: SSH out of the lab is blocked. A GitHub App works over
HTTPS and is also not tied to a person.

## 15. The Private AI namespace has a reservation

Private AI Services runs as vSphere Pods, and a vSphere Pod's requests
are reservations. With none, its pods stay `Pending`. `private-ai`
reserves 15 GHz and 16 GiB, and the org's quota allows it.

Why: 5 GHz is the documented minimum. At 5 GHz a rolling update has no
room for the new pods.

## 16. Secrets stay local; state is remote: see 22

Passwords and keys are in `terraform.tfvars`, `backend.hcl`, and
`.secrets/`, all ignored by git.

## 17. Terraform resources have descriptive names

Not `this`. A rename of a resource that is already in state gets a
`moved` block. `terraform/cloud-admin/org` still has resources named `this`.

## 18. Argo CD has health checks for the database, Private AI Services, and the model

Argo CD has no built-in check for `PostgresCluster`, `PAISConfiguration`,
or `ModelEndpoint`, and called each healthy as soon as the object
existed. The Argo CD manifest adds one Lua script for all three, on the
`Ready` condition they share.

It reports progressing, never degraded. While DSM builds a database it
sets `Provisioning` to reason `Failed`, and Private AI Services reports
`validationError` until its Secret exists. Both clear by themselves.

Why: sync waves depend on it. `gitops/private-ai/` uses wave 0 for the
database, 1 for Private AI Services, and 2 for the model, and a wave
starts only when the one before it is healthy.

Cost: a resource that is truly stuck shows as progressing, with the real
reason in the message.

The script was run against status copied from the lab, for the ready and
the not-ready case of each kind.

## 19. Private AI Services reaches its database by a Service name

`PAISConfiguration` takes the database host as plain text, and DSM
assigns the address when it creates the database. The first version
committed the address to git afterwards, which made a rebuild a two-step
job.

Now `gitops/private-ai/database-service.yaml` gives the database a fixed
name:

- A Service `pais-db` with no selector.
- An Argo CD sync hook Job that reads the address from the
  `PostgresCluster` status and writes it into the Service's Endpoints.
- `dnsNames: [pais-db]` on the `PostgresCluster`, so the database's
  certificate is valid for the name and `sslMode: VerifyFull` still
  holds.

Why: no address in git, and a rebuild needs no manual step. It needs no
DNS record; the name comes from the Supervisor's cluster DNS.

Checked in the lab before building it: from a Private AI Services pod,
the name resolved, the connection reached the database, and a TLS
handshake verified the name `pais-db` and refused a wrong one.

Cost: a ServiceAccount, a Role, and a Job, and one public image
(`alpine/k8s`) that the lab must be able to pull. Argo CD does not track
Endpoints, which is why the Job's write is not undone, and also why
Argo CD cannot create them itself.

## 20. Terraform creates the Private AI Services login Secret

`pais-static-credentials` holds a password hash. Terraform creates it in
the `private-ai` namespace from `terraform.tfvars`. Argo CD does not
manage it.

Why: a hash does not belong in git, and one Secret does not justify a
secrets manager.

## 21. The shop users VM and the catalog are gitops, and they name no org

The recording applies this repository to a new organization. The users
service is a VM Service VM, and the catalog is a DSM PostgresCluster.
Both follow the rules already used for Private AI Services: no namespace
in the file, no address in git, the Service name is what the app already
calls (`users-service`, `postgres-service`).

The container users Deployment and the container database stay in
`app/music-store` as the earlier shape. `kustomization.yml` no longer
lists them. Argo CD syncs `gitops/music-store/`, not that directory.

The chat secret is not in git, for the same reason as the Private AI
Services password hash. Its base URL is the ingress of the Private AI
Services this repository deploys, and the model name is `qwen`.
## 22. Terraform state is in the lab's Gitea

Both roots use Terraform's `http` backend against the Terraform state
registry of the lab's Gitea server, under the organization `the-goad`.
It stores the state, locks it, and keeps every version.

One shared Gitea user, `goad-terraform`, holds the token. It is in a
team of the organization with write access to packages. The address and
the settings are in `backend.tf`, in git. Only the token is in
`backend.hcl`, which git ignores. At first the address was kept out of
git too; it moved in when the other lab values did (24).

Why: more than one person applies now, and state had to leave one
laptop. No S3 is available. GitHub has no Terraform backend. Gitea was
already running, so there was no new service and no new account.

Why not the Kubernetes backend in another org: VCF Automation tokens are
short-lived, so every run would need a wrapper to make a fresh
kubeconfig, and the state would depend on that other org.

Why a shared user: nobody has to be set up in Gitea to apply.

Cost: no record of who changed state. One token leak exposes all of it,
and the state holds passwords and a private key. The token allows
package writes in the whole organization; Gitea has no finer scope. The
state is safe from a teardown of the `goad` org, not from the loss of
the lab git server.

Found on the way: membership of the organization is not enough. The
user's team must have the Packages unit set to Write. With less, reads
work and the lock call answers `401 reqPackageAccess`, which Terraform
reports as "HTTP remote state endpoint requires auth".

## 23. Namespace names are read through one local value

`local.namespace_names` in `terraform/platform-engineer/namespace.tf` is
a map of every namespace's generated name. The kubeconfig lookups, and
everything else that needs a name, read it from there and not from the
namespace resource.

Why: Terraform looks up the address of a namespace's Kubernetes API with
a data source. A data source that refers straight to a resource is not
read until apply when that resource has any pending change. Adding a
namespace, or resizing one, is a pending change. The lookups were put
off, and with no address every existing Kubernetes object failed to
refresh:

    Get "http://localhost/api": dial tcp 127.0.0.1:80: connection refused

A data source that reaches the same value through a local value is read
at plan time, as long as the value is known. The names are known: they
do not change when a namespace is resized or a sibling is added.

`lazy_load` on the `kubectl` provider is still needed for a build from
nothing, where the names do not exist yet.

Checked in throwaway configurations and then in the lab, plan only: add
a namespace, resize `platform`, resize another namespace, all in one
plan.

What was tried and dropped:

- `depends_on`. It makes Terraform put the lookup off in more cases.
- Two resources for the namespaces, the ones Terraform uses and the
  rest. It fixed adding a namespace and not resizing one.
- A `terraform_data` resource per name. It works, and it is one extra
  resource for each namespace Terraform uses.
- A module per namespace. It works for the same reason the local value
  does, and it is more to read.

## 24. The inputs are shared files, not personal ones

With remote state, everyone applies to the same lab from their own
machine. Terraform makes the lab match the inputs of whoever applies.
So `terraform.tfvars` in both roots, the deploy key, and the Private AI
Services password hash are one copy for the team, kept in the password
manager.

Why: a different deploy key replaces the one in Argo CD's repository
Secret, and Argo CD stops reading git. A new hash of the same password
is still a different value, because the hash is salted. A different
`cloud_admin_password` changes the password of `cloud-admin`, and
stage 2 and everyone else's login fail.

This follows from two earlier choices: shared accounts instead of one
per person (4, 22), and secrets kept out of git (16).

The lab values that are not secret are in `lab.auto.tfvars` in each
root, in git. Terraform loads that file by itself. They cannot differ
between people, and a change to one is a commit. Only the passwords, the
hash, the deploy key, and the state token are passed around.

Cost: the repository now names one lab: its VCF Automation address,
region, and policy names. `gitops/` already did. It is a private
repository; this is not for a public one.

## 25. Terraform runs in GitHub Actions, on a runner in a vCenter namespace

There is one workflow for each persona:
`.github/workflows/cloud-admin.yml` and `platform-engineer.yml`. Each
runs only its own Terraform root, and only when a person starts it, from
the Actions page or with `gh workflow run`. A run plans. It applies only
if `apply` is ticked, and only on `main`.

The jobs run on a self-hosted runner in the lab. GitHub's own runners
cannot reach VCF Automation or the lab's Gitea server. The runner is
[supervisor-github-runner](https://github.com/warroyo/supervisor-github-runner):
a plain Deployment of vSphere Pods, registered to the GitHub
organization.

A third Terraform root, `terraform/runner`, builds the runner: its
Supervisor Namespace, the Secret, and the Deployment. That namespace is
made in vCenter, not through VCF Automation.

Why a vCenter namespace: the runner is what runs Terraform, so it cannot
depend on anything the two persona roots make. The cloud admin root
creates the org `goad` and can destroy it. A runner in a namespace of
that org could not do the first build, and a destroy would delete the
runner in the middle of its own job. A namespace in another VCF
Automation org would survive that, but it would still need VCF
Automation to be up, and the cloud admin root changes provider-scope
settings there. A vCenter namespace depends only on the Supervisor.

Why Terraform for the runner, and not a script and `kubectl apply`: the
rest of the repository is Terraform. A plan shows drift, and a destroy
removes all of it.

Why that root is applied by hand: no workflow can run it, because it
builds what the workflows run on. It is not a persona.

Why its state is in Gitea with the other two, and not local: the state is
shared, like the others. There is no circle. Gitea does not depend on the
runner, and a machine reaches Gitea without it.

Why the root reads the Deployment from supervisor-github-runner at a
pinned commit, and does not copy it or follow `main`: a copy goes stale,
and `main` would restart the runner in an apply for something else. The
released `alekc/kubectl` provider, 2.4.1, has no kustomize data source,
so Terraform reads the two files with `http` and sets the replicas
itself.

Why the job's disk is the pod's own, and not a volume claim: a claim
outlives its pod, and someone must delete it. The pod's own disk is
deleted with the pod. A job keeps nothing there anyway: state is in
Gitea. The default, about 250 MB, is too small for one root's
providers, so the pod asks for 4 GB. That is set in
supervisor-github-runner, not here: every user of that runner has the
same problem.

Why by hand, and not on a pull request or a push: not yet. The lab is
shared, and an apply creates and deletes a real org. Until the team has
seen the runs work, a person decides each one. Cost: a merge to `main`
does not apply itself, so `main` and the lab can differ until someone
runs the workflow.

Why one workflow for each persona, and not one with two jobs: the demo
shows each persona doing its own work. The cloud admin's run must not
also be the platform engineer's. Cost: nothing orders the two. On a
first build the platform engineer's fails until the org exists. Run the
cloud admin's first.

The split is for the story, not for security. The secrets are the
repository's, so each workflow could read the other persona's. That is
accepted: this is a mock of two teams, not a real separation.

Why not Atlantis: it needs a webhook from GitHub into the lab. A runner
only makes outbound connections.

Cost: the GitHub App is made by hand, with one confirmation in a browser,
because GitHub has no API for it. `scripts/create-github-app.py` does
the rest. The team shares two more secrets: the vCenter password and
the App's private key. The organization is on the free plan and the
repository is private, so there is no required review before an apply:
anyone who can write to the repository can start one.

Second look when: the team trusts the runs, the organization has a plan
with environment protection rules, or the runner needs more than a few
replicas. The first is when a pull request can plan and a push to `main` can apply.
The second allows a reviewer before apply. The third is where a controller
that scales on the job queue is worth its weight.

## 26. The cloud admin is two roots: org, then org-config

`terraform/cloud-admin/org` (state `goad-cloud-admin`) creates the org,
VCF SSO, quota, networking, and the DSM policy.
`terraform/cloud-admin/org-config` (state `goad-cloud-admin-org-config`)
configures things inside the org. `cloud-admin.yml` runs them as two jobs,
`org` then `org-config`.

Why: the first root logs in to the provider (System) org, and the second
logs in to the org itself, as `cloud-admin`. A provider cannot log in to
an org that its own apply has not created yet. Two roots also keep the
work inside the org out of the destroy of the org.

Cost: two states, two `terraform.tfvars`, and teardown in order:
platform engineer, then `org-config`, then `org`. Teammates who had the
old single root move their `backend.hcl` and `terraform.tfvars` into `org/`
and run `terraform init` there again.

Look again if: the provider can configure an org it creates in one root.

## 27. VCF SSO is wired through VCF Operations' internal API

`oidc.tf` creates the org's OIDC client in the VCF Identity Broker with
TerraCurl, at `/suite-api/internal/vidb/oauthclients` on VCF Operations,
with the header `X-vRealizeOps-API-use-unsupported`. Then it sets
`vcfa_org_oidc`.

Why: VCF Automation allows one local user for each org, so people must
come in through AD and the Identity Broker. No provider can create the
client, and the documented broker API needs a client token of a tenant
administrator, which does not exist yet.

Cost: the API is internal and unsupported, and it can change in another
release. `oidc.tf` then fails and needs a fix.

Look again if: a provider or a documented API creates the client.

## 28. The platform engineer logs in with an AD service user's API token

`terraform/platform-engineer` uses `vcfa_api_token`: a user API token of
the AD service account `svc.platform_engineer@set.lab`. `org-config`
imports that user as Organization Administrator. The token is made by
hand once, in the UI, as that user.

Why not a VCF Automation service account: its session cannot manage other
service accounts (403 `SERVICE_ACCOUNT_SIMPLE_VIEW`), and the Argo CD step
in `argocd.tf` needs that. A user API token session can.

Why not the local user: the org has one, `cloud-admin`, and it belongs to
the cloud admin. The old local user `platform-admin` is deleted.

Cost: one manual step, and the token is a shared secret
(`PLATFORM_ENGINEER_VCFA_TOKEN` in GitHub). A new AD user can log in only
after the Identity Broker syncs the directory.

## 29. AgentMinder is installed by its own cloud admin root

`terraform/cloud-admin/agentminder` (state `goad-cloud-admin-agentminder`)
installs AgentMinder with Helm. The cluster it runs on, with its project
and namespace, is made by `org-config`. `cloud-admin.yml` runs it as a
third job, `agentminder`, after `org-config`.

The root reads the project, namespace, and cluster names from the state
of `org-config` with `terraform_remote_state`. It gets the cluster's
admin kubeconfig with `vcfa_vks_cluster_kubeconfig`, a client
certificate that does not expire during a long install. It makes one
pull secret, `ssp-registry`, for Broadcom's registry, and both charts
read it through `existingSecrets`.

Why a separate root: the Helm and Kubernetes providers need the
cluster's address. A provider configured from a resource that the same
apply creates fails at plan. It is the same problem as decision 23. A
second root plans only after the cluster exists.

Cost: a third state and a third `terraform.tfvars`. The remote state
read cannot use `backend.hcl`, so a person must also
`export TF_HTTP_PASSWORD=<the state token>`. The workflow already sets
it. Two more repository secrets, `SSP_REGISTRY_USERNAME` and
`SSP_REGISTRY_PASSWORD`.
Teardown order: platform engineer, `agentminder`, `org-config`, `org`.

Look again if: the provider can configure Helm from a cluster that the
same apply creates.

## 30. AgentMinder is installed small

The `ssp` chart runs with `ssp.deployment.size` `demo`, one Hazelcast
member, and `aigateway` and `mcpserver` on. `otelCollector`,
`custommetrics`, `selfserviceconsole`, and `fluent-bit` are off.
`localLlm`, the model for the MCP playground, and `global.observe` are
off by default. The database volume is 20Gi, not 80Gi. The VKS cluster
has one control plane and two workers.

Each `ssp` service asks for 100m CPU, not the chart's 400m (1000m for
`iarisk`). With the chart's requests the services did not fit on two
workers: `aigateway` and `iarisk` stayed Pending with "Insufficient cpu".
At demo load each service uses under 15m. The limits stay the chart's.

Why: this install is for the demo only. It shows the agent gateway and
the MCP server, not the observability pipeline or the console. Fewer
components need fewer nodes and less disk, and the lab is shared.

Cost: no metrics, no log shipping, no local model, and one replica of
each service, so nothing survives a lost node. With low requests the
scheduler packs the services onto two workers, and under real load they
compete for CPU. The namespace `ssp` is
Pod Security `privileged`, like the lab's other AgentMinder, because a
stricter profile has not been tried.

Look again if: the demo needs the playground or the dashboards, or the
cluster runs out of room.

## 31. AgentMinder's DNS name comes from Avi, through AKO

The ingress controller's Service in the AgentMinder cluster has
`loadBalancerClass: ako.vmware.com/avi-lb` and the annotation
`external-dns.alpha.kubernetes.io/hostname: agentminder.goad.gpu.set.lab`.
The cluster's own AKO serves it and puts the name on the Avi virtual
service. Avi DNS is authoritative for `goad.gpu.set.lab`, and the lab DNS
delegates that zone to it, so the record exists as soon as the virtual
service does.

Why: no DNS step by hand, and the record follows the address if the
Service is made again. A VKS cluster's AKO has `defaultLBController`
`false`, so a LoadBalancer Service with no class goes to the Supervisor,
whose virtual services get no FQDN. Tested first with a throwaway
Service: address and record within a minute, and nginx answered through
it.

Cost: the name must be in `goad.gpu.set.lab`. `loadBalancerClass` cannot
change on an existing Service, so moving a Service from the Supervisor to
AKO means deleting it first. ingress-nginx is no longer the default
IngressClass; AKO's `avi-lb` is.

## 32. The music store's VKS cluster is gitops

`gitops/music-store/cluster.yaml` is a plain `cluster.x-k8s.io/v1beta2`
Cluster named `music-store`: class `builtin-generic-v3.7.0`, Kubernetes
v1.36.2+vmware.2, one control plane and two workers, all best-effort-medium,
Antrea, sync wave 0. Argo CD syncs it with the Application `music-store`,
as it does the catalog. The containers in `app/music-store` are not
deployed onto it by this Application. Decision 34 does this.

The names in the file are the Supervisor's, not the org's (decision 21:
no namespace, no address).

No health check of our own: the Argo CD that VCF ships has a built-in one
for Cluster. Upstream Argo CD calls a cluster Healthy at phase
Provisioned, before the nodes are up. The VCF build waits until the
cluster is ready: a cluster at phase Provisioned with no control plane
shows Progressing, "Waiting for Cluster to be Ready".

The `music-store` namespace limits are now 40000M CPU, 48Gi memory, and 150Gi storage, to
fit the cluster. Storage stays at 150Gi so the sum of the namespace storage limits
stays within the org's 1 TiB region quota.

Why not a `vcfa_vks_cluster` in Terraform, as for AgentMinder's cluster in
`terraform/cloud-admin/org-config`: the platform engineer owns what runs in
the `music-store` namespace, and decision 13 makes git the source after
Terraform. `docs/master-design-v5.md` has the platform engineer deploy VKS
clusters, and the script has the VKS cluster in the deploy. Why the same
Application and no new one: decision 13, the smallest thing. Why wave 0:
the cluster needs nothing else and takes the longest.

Cost: on a first build the catalog Jobs in waves 1 and 2 wait for the
cluster too, about 15 minutes.

Look again if: the containers move onto the cluster (Argo CD needs the
cluster registered as a destination; decision 34 does this), or the
region quota grows.

## 33. The org's VM image is uploaded by the platform engineer Terraform

The users VM in `gitops/music-store` never came up in the lab. Argo CD
failed with `no VM image exists for "ubuntu-24.04-cloud" in namespace or
cluster scope`. The goad org had no content library, so no image.

`terraform/platform-engineer/images.tf` creates the org content library
`goad-images` and uploads Ubuntu's noble cloud OVA as the item
`ubuntu-24.04-cloud`. The library has `auto_attach = true`, so it is
attached to every namespace in the org. A `terraform_data` with
`local-exec` downloads the OVA with `curl` into
`terraform/platform-engineer/.images/`, which git ignores, on the machine
or runner that first applies. After that nobody needs the file: the
provider reads `file_paths` only to create the item. The library's
storage policy is the lab value `content_library_storage_policy`, by its
vCenter name, because a tenant's `vcfa_storage_class` lookup takes the
policy name, not the Kubernetes name.

The same fix changes the className of the users VM from
`best-effort-xsmall` to `best-effort-small`. The org's VM classes
(`vm_class_names` in `terraform/cloud-admin/org/lab.auto.tfvars`) do not
include xsmall.

Why Terraform and not gitops: a content library is an org object in VCF
Automation, not a Kubernetes object in a namespace, and Argo CD cannot
make it. Why the platform engineer root and not the cloud admin: the
library serves the platform engineer's namespaces, and the platform
engineer is an Organization Administrator. Why an upload and not a
subscribed library: the published libraries on vc01 belong to another
org's hand-made setup. An upload from Ubuntu needs nothing else in the
lab.

Cost: the first apply downloads about 570 MiB and uploads it, several
minutes. The machine or runner needs `curl` and outbound internet to
cloud-images.ubuntu.com, for that first apply only.

Look again if: the lab gets a provider content library with the image,
shared with orgs.

## 34. The music store is split between the platform engineer and the developer

Decision 45 gives this deploy to the platform engineer, moves the users
VM back into `music-store`, and renames `app/` to `gitops/music-store-apps/`.

The platform engineer keeps the Application `music-store`, which syncs
`gitops/music-store/`: the VKS cluster `music-store` and the DSM catalog
database. The users VM moved out of it. The developer owns
`gitops/music-store-dev/`, with two Applications:

- `music-store-dev-vm` syncs `gitops/music-store-dev/users-vm/` into the
  `music-store` Supervisor Namespace. It holds the users VM and the Job
  `shop-endpoints`.
- `music-store-dev-app` syncs `gitops/music-store-dev/app/` into the
  namespace `music-store` of the VKS cluster, with `CreateNamespace=true`.
  It is a kustomization of `app/music-store` plus selectorless Services
  `postgres-service` and `users-service`.

Why two Applications: they have two destinations, the Supervisor
Namespace and the VKS cluster, and an Application has one. Why Terraform
creates them: the Supervisor Namespace name is generated (decision 13), so
git cannot name it. Terraform also creates the ManagedEntity
`music-store-cluster`, which registers the VKS cluster with Argo CD. It
reads the cluster name from `gitops/music-store/cluster.yaml`.

Why the Job: pods on the cluster call `users-service` and
`postgres-service`, but the users VM and the catalog are in the
Supervisor Namespace, outside the cluster. The Job in wave 1 of
`music-store-dev-vm` reads the VM's load balancer address and the
catalog's Endpoints there. Then it uses the kubeconfig Secret
`music-store-kubeconfig` to write Endpoints with the same names into
`music-store` on the cluster. It creates that namespace if it is missing.
The Job lives with the developer because the developer owns the wiring of
the application. No address is in git (decision 21).

The VKS cluster has no default StorageClass, so a patch in the
kustomization sets `storageClassName` on every PVC. The chat service is
not in `app/music-store/kustomization.yml`: the walkthrough script
deploys it to Tanzu with `cf push`. The container database and container
users are not listed either, because the catalog and the users VM
replace them.

Why retry and not order: the developer's Applications need the platform
engineer's cluster and catalog, and Argo CD cannot order one Application
against another. Both have `syncPolicy.retry`: limit 10, backoff 1m, factor
2, maximum 10m.

Cost: the Job holds the VKS admin kubeconfig. The Endpoints refresh only
when `music-store-dev-vm` syncs, so if DSM or the VM's load balancer
address changes, the developer must sync it again. The users VM moves
from the Application `music-store` to `music-store-dev-vm`. The platform
Application has `prune=true`, so on merge Argo CD deletes the VM, its
VirtualMachineService `users-service`, and the Secret
`music-users-bootstrap`, and `music-store-dev-vm` makes them again after
the platform engineer apply. The music store was not in use yet, so the
rebuild was accepted. A store in use would need
`argocd.argoproj.io/sync-options: Prune=false` on those three objects
before the merge, and the annotation removed after the new Application
adopts them.

Look again if: the lab gets a way to order Applications across
destinations, or the Job's kubeconfig access is too broad for the demo.

## 35. Platform engineers author kro APIs from the project kro-authors

The kro Supervisor Service (github.com/warroyo/kro-supervisor-service,
v1.2.0) has a multitenancy mode. Editors and admins of a VCF Automation
project listed in its values `multitenancy.orgs[].authorProjects`, by
project uid, can create ResourceGraphDefinitions in their org's API group.
Here that is `goad.kro.run`. RBAC on the Supervisor is bound to the exact
group that VCF Automation sends for the project. An admission policy keeps
each org to its own group and checks what an RGD may contain.

`terraform/cloud-admin/org-config/kro.tf` creates the project `kro-authors`.
It is org-level setup, so the cloud admin's root makes it, like the
cloud-admin project. Access goes to a group, not to single users: the VCF
SSO group `kro_author_group` (`ans-platform-engineer@set.lab`) gets the
project role `edit`. That is enough, because VCF Automation sends the same
`edit-<project>` group to the Supervisor for edit and admin. The binding is
named `cci:group:set.lab:ans-platform-engineer`, as VCF Automation requires.
The automation user `svc.platform_engineer@set.lab` is an Organization
Administrator, so it already counts as an editor. Argo CD reaches the
Supervisor as that user, so it can sync RGDs pointed at the kro-authors
namespace.

The root also makes a small Supervisor Namespace, `kro-authors-xxxxx`
(class small, 2000M CPU, 4Gi memory, 10Gi storage), so authors have a
kubectl context in the project. RGDs are cluster-scoped and use no quota.
Instances of `goad.kro.run` kinds go in the org's other namespaces.

The service and its values are set on the Supervisor by the vSphere admin,
through the vCenter API, not by this repo. The goad entry is org `goad`, id
the goad org UUID, and `authorProjects` with `name: kro-authors` and `id`
the project's `metadata.uid`. The script `scripts/multitenancy-values.sh
<namespace-context> goad` in the service repo prints it. If the project is
deleted and recreated, it gets a new uid, and authors are refused until
the values are updated.

Cost: a namespace kept only for the kubectl context. The group must be
imported into the org by hand before the apply, or the binding is refused.

Look again if: the vcf CLI or VCF Automation can give a project context
without a namespace, or the group should be imported by Terraform.

## 36. Platform engineers are an AD group, not users named one by one

`terraform/cloud-admin/org-config/users.tf` imports the VCF SSO group
`platform_engineer_group` (`ans-platform-engineer@set.lab`) into the org
with the org role Organization User, and gives the group its roles:
`admin` of `default-project` and `edit` of `kro-authors`. The Argo CD
policy in `terraform/platform-engineer/manifests/argocd.yaml` gives the
same group `role:admin`. Adding a platform engineer is now an AD change,
not a Terraform change. This replaces `platform_engineers` and the
`kro_author_group` variable, and answers the "Look again if" of decision
35: Terraform imports the group.

TerraCurl's `import` only sets the ID, and every other attribute forces a
replacement. So the group that was added by hand was deleted and created
again by Terraform. The users that were imported one by one stay in the
org: a `removed` block with `destroy = false` dropped them from state.
Their user role bindings in `default-project` are destroyed. The
`removed` block and the `moved` block for the `kro-authors` binding were
applied once in the lab and then deleted from the code.

All org IAM, users, groups, and their project role bindings, is in
`users.tf`, also for projects that other files create, such as
`kro-authors`.

Cost: a member gets the group's roles only after a UI login to VCF
Automation, because VCF Automation updates group membership only then.
Deleting and creating the group again also unlinks members until their
next login.

Look again if: the Argo CD `groups` claim from VCF Automation does not
carry the org group's name. Then Argo CD has to map a different value.

## 37. One owner per gitops directory; the incident demo is not gitops

Two moves on 2026-10-22 put the developer's `app/` and `users-vm/` under
the platform engineer's `gitops/music-store/`, and the incident demo
under `gitops/incident-demo/`. Both are undone:

- `gitops/music-store-dev/app/` and `gitops/music-store-dev/users-vm/`
  are the developer's directories again, as in decision 34. The shop's
  source and covers stay in `app/`, with its manifests: Argo CD's
  kustomize does not load files from outside the directory it syncs.
- The Application `music-store` no longer sets `directory.recurse =
  false`. It syncs `gitops/music-store/` like every other namespace
  (decision 13), and that directory has no subdirectories.
- The incident demo is `incident-demo/` at the repository root. A person
  runs it (`apply.py`, `push.py`, `walk/demo.sh`), so by decision 10 and
  the placement rule in the README it is not under `gitops/`.
- No password is in git. The shop's catalog password was the literal
  `music_password`, in `catalog-init` and in `app/music-store`, and the
  Secrets `store-db` and `metal-oracle-model` were made by hand, so a
  rebuild in a new org had the storefront and chat pods waiting on
  Secrets nobody made. Decision 38 has how they are made now.
- The snapshot `app/backup/music-store-2026-10-22.json` is removed. It
  held live addresses (decision 21) in a synced directory. Git history
  has it.
- `app/music-store/` is the earlier shape and the Antrea policy test. It
  is not deployed.

Why: one owner and one Application per directory means no Application
can adopt or prune another owner's files. With the developer's files
inside the platform engineer's directory, only a recurse flag kept the
platform Application, which prunes, away from them.

Cost: the platform engineer Terraform must apply after the merge so the
two developer Applications point at the new paths. Until then they show
a comparison error for a missing path and change nothing in the lab.
`incident/` at the root was the earlier incident design. Decision 39
removes it.

Look again if: the incident demo becomes something Argo CD syncs. Then
its manifests move under `gitops/` and its scripts stay out.

## 38. Secrets go from GitHub to Secret Store, and ESO and the vault injector read them

No password or key is in git (decision 37). The shop's two secrets go:

1. **GitHub to Terraform.** The repository secrets `MUSIC_STORE_DB_PASSWORD`
   and `MUSIC_STORE_CHAT_API_KEY` reach the platform engineer workflow as
   `TF_VAR_*`; on a machine they are in `terraform.tfvars`. The chat's URL
   and model name are not secret and are lab values in `lab.auto.tfvars`.
2. **Terraform to Secret Store.** `terraform/platform-engineer/secrets.tf`
   writes the `KeyValueSecret`s `music-store-catalog` (password) and
   `music-store-chat` (base-url, api-key, model) into the `music-store`
   Supervisor Namespace. Secret Store keeps the values in OpenBao, not in
   etcd, and never returns them on read, so Terraform ignores
   `spec.data` when it compares the live object.
3. **Supervisor Namespace: the vault injector.** `catalog-init` has the
   annotations of the Supervisor's own injector. The agent logs in with
   the namespace's role (the namespace name) and writes the password to
   `/vault/secrets/catalog`, which psql reads and sets on `music_user` on
   every sync.
4. **VKS cluster: ESO.** The `external-secrets` addon is installed by an
   `AddonInstall` in `gitops/music-store/`, selected by a label on the
   cluster. The `ClusterSecretStore` `secret-store` in
   `gitops/music-store-platform/` reads Secret Store, and the
   `ExternalSecret`s in `gitops/music-store-dev/app/` make `store-db` and
   `metal-oracle-model`.

Who owns what: the platform engineer owns the values, the KVs, ESO and
the store. The developer only names the secrets the app needs. Terraform
does the two things git cannot: the values, and the generated namespace
name.

**The namespace name.** The injector's role and path, the store's auth
mount and role, and the `ExternalSecret` keys all contain the Supervisor
Namespace name. The manifests carry the placeholder
`SUPERVISOR_NAMESPACE`, and Terraform's Applications replace it with
`kustomize.patches`. So `gitops/music-store/` is now a kustomization, and
the Application `music-store` is the only one of the per-namespace
Applications with patches.

**What the cluster already has.** The vault-injector addon, which VKS
installs on every cluster, makes `vks-vault-injector/secret-store-service`
(its Endpoints are the Secret Store load balancer, and its name is in the
server certificate), `vks-vault-injector/server-cert`, and the token
reviewer `kube-system/openbao-auth`. So the store has no address or
certificate in git, and its ServiceAccount `secret-store-reader` needs no
`system:auth-delegator` binding. Checked in the lab on 2026-10-26: a token
of `default/default`, which has no such binding, logged in to
`auth/kubernetes-<namespace>-music-store` with role
`<namespace>-music-store`, with TLS verified against that certificate. The
certificate is the self-signed server certificate, not a CA: curl refuses
it, OpenSSL and Go accept it.

**What the injector needs on a vSphere Pod.** Also checked on 2026-10-26,
with a throwaway KV and pod. Without `agent-requests-cpu` and
`agent-requests-mem` set to `0`, the pod is not scheduled: a vSphere Pod's
requests are reservations, and the namespace has none. The injector's
default agent image is on `vsphere-docker-virtual.packages.vcfd.broadcom.net`,
which does not resolve in the lab, so the agent is
`quay.io/openbao/openbao:2.4.4` (quay has no 2.4.5). `agent-pre-populate-only`
leaves no sidecar, so the Job can finish.

Why not a Job that makes the password, which this branch first did: the
value then exists only in the lab, a rebuild makes a new one, and a Job
that writes Secrets is the custom glue that ESO replaces. Why not
`hostAliases` to the Secret Store address, as in the earlier ESO setup on
warroyo's blog: the cluster already has a Service with that address.

Cost:
- A changed value reaches pods only when they restart. The database gets it
  at the next sync of `music-store`.
- One more public image, from quay.
- Argo CD must never own a `KeyValueSecret`: the API ignores label
  selectors, so a pruning tool deletes every KV in the namespace. Only
  Terraform writes them.
- Secret Store's aggregator does not renew its OpenBao token, so KV writes
  can fail with 403 until it is restarted. That is a known bug, filed with
  Broadcom.
- On the first sync, the Applications with ESO resources fail with
  `no matches for kind`, until the addon has installed ESO's CRDs. Argo
  CD's retry syncs them about two minutes later.

Checked at the rollout on 2026-10-27: Argo CD's identity may create the
`AddonInstall`, and the manager's labels on it don't make Argo CD report a
difference. ESO took over the hand-made `store-db` and
`metal-oracle-model` in place, so they did not have to be deleted first.

Look again if: the injector's default image resolves in the lab, or VKS
gives clusters a ClusterSecretStore of its own.

## 39. One incident demo tree: `incident-demo/`

`incident/` is removed. It was the first incident design, from
2026-10-14: agents on the VKS cluster `goad-store`, with placeholder
images and a placeholder namespace, and it was never applied.
`incident-demo/` replaced it on 2026-10-22. That design runs the agents
in the Tanzu Platform org `Goad` and Zammad and Grafana beside the shop.
Most of `incident/` had a newer copy in `incident-demo/`.

The one part still in use was the AgentMinder sidecar. `push.py` copied
`mcp_bridge.py` and `run-sidecar.sh` from a checkout of `incident/` at a
fixed path under `/tmp`. They and their test now live in
`incident-demo/tanzu-agents/sidecar/`, next to `push.py`, which reads them
from the repository.

`incident-demo/` stays at the root (decision 37): a person runs it, and it
is a whole demo, not a helper script for `scripts/`.

Why: two trees for one demo, with one silently feeding the other through
`/tmp`, means an edit can land in the copy that isn't used.

Cost: the earlier design's code is no longer in the tree. Git history has
it, up to the commit before this decision: the orchestrator, the
fault-injection scripts, the Grafana boards, and the `goad-store` cluster.
The sidecar test needs the AgentMinder SDK, which isn't on public PyPI, so
it only runs where the SDK is unpacked.

Look again if: part of the earlier design, such as fault injection, comes
back. Bring it into `incident-demo/`, not a second tree.

## 40. Tanzu Platform apps: Terraform makes the space, a workflow pushes

The incident demo's nine Cloud Foundry apps were pushed by hand with
`incident-demo/tanzu-agents/push.py`, which also made their services and
set their env with `cf curl`, from files under `/tmp` and `~/.cache`.
Now the work is split by who owns it:

- The platform engineer's Terraform (`terraform/platform-engineer/tanzu.tf`)
  owns the space `metal-music-app-agentic-system` and its six
  user-provided services. It reads org `Goad`, which exists already. The
  space and services were imported, not made again.
- `.github/workflows/tanzu-apps.yml` owns the apps. It pushes
  `tanzu/metal-music-app-agentic-system/manifest.yml` on every change to
  that directory on `main`, and adds the network policies.
- `tanzu/<space>/` is a new top-level directory: one directory per app,
  pushed as it is. `stage.sh` copies in only what several apps share. The
  sidecar from decision 39 is in `shared/sidecar/`.

Every login is `goad-deployer`, a Tanzu Hub OAuth app with admin roles,
for now. The foundation takes only its client assertion secret. The
Tanzu cf CLI signs that itself, so `tanzu-apps.yml` logs in with the CLI
(the `cf-login` action). The CLI comes from the foundation at run time
(`links.tanzu_cf_cli` on the CF API root), so it always matches the
foundation. The `cloudfoundry` provider cannot sign the assertion, so the
`cf-token` action signs it with `openssl` and gives Terraform the token.
Using the CLI for that was tried first: on a fresh `HOME` the CLI installs
about 140 MB of plugins before it logs in, which took four minutes on the
runner, and a runner pod was evicted for memory pressure during it. The
CLI's `HOME` is on the runner's work disk for the same reason.

The apps' secrets are GitHub secrets `INCIDENT_*`, passed to `cf push`
in a vars file that is deleted after the push. Three of them are also in
the services, so both workflows read them. The AgentMinder SDK is a
private GitHub package, `ghcr.io/modern-apps-5/agentminder-sdk`, filled
by `scripts/mirror-agentminder-sdk.sh`: it is not on public PyPI, and the
runner has no Docker and no Broadcom registry token.

Why GitHub secrets and not CredHub-backed services: the apps read env
vars. Services would mean changing every app to read `VCAP_SERVICES`.
Music store secrets come from GitHub secrets too (decision 38).

Why a workflow and not the `cloudfoundry` provider's app resource: an
app push is a deploy that should follow every change to the code, not a
person starting a plan. Terraform still owns what outlives a deploy.

Cost: a secret changed in GitHub reaches the apps only on the next push,
and the three shared ones need both workflows to run. The AgentMinder
client IDs, secrets and gateway URLs are not GitHub secrets: the cloud
admin's Terraform puts them in user-provided services (decision 41).
`goad-deployer` has far more
rights than a push needs.

Look again if: Tanzu Hub service accounts get narrower roles, the
`cloudfoundry` provider learns `private_key_jwt`, or AgentMinder clients
move to Terraform.

## 41. The cloud admin registers AgentMinder in Terraform, with restapi

`incident-demo/agentminder/register.py` made the incident demo's
AgentMinder objects by hand. Now `terraform/cloud-admin/agentminder-registration`
makes them, and the fourth job of `cloud-admin.yml` runs it. It makes the MCP resource
servers `goad-avi-mcp`, `goad-k8s-mcp` and `goad-vcf-mcp`, the clients
`py-goad-lb`, `py-goad-k8s`, `py-goad-vcf` and `py-goad-incident-response`,
one role policy for each diagnostic client, and each client's entry in
`AuthClientPolicy`. The state is `goad-cloud-admin-agentminder-registration`.
`register.py` is removed.

**Why the cloud admin.** The cloud admin owns AgentMinder, and the incident
demo's diagnostic agents are the cloud admin's troubleshooting tools. It
already has the VCF Automation and cluster login. Issues 3 and 38 framed
this as a security admin persona. That persona is not built.

**Why a separate stage.** The `restapi` provider's configuration needs
AgentMinder running, and stage 3 creates it. In one root, a fresh build
could not plan.

**The login.** The root logs in to VCF Automation as `cloud-admin`, as stage
3 does, reads `org-config`'s state for the cluster names, and gets the
AgentMinder cluster's kubeconfig with `vcfa_vks_cluster_kubeconfig`. A
`kubernetes_secret_v1` data source reads the `ssp` chart's Secret
`ssp-ssp-secret-defaulttenantclient`, in the namespace `ssp`. That is the
default tenant's admin OAuth client, and it configures the `restapi`
provider. Stage 3 has no outputs and passes no secret through remote state.
AgentMinder has no service accounts yet.

**The handoff to the apps.** AgentMinder returns each client's secret on
read. This root also uses the `cloudfoundry` provider
(`cloudfoundry.tf`, token from the `cf-token` action) and makes one
user-provided service for each diagnostic agent, `am-lb-diagnostic-agent`,
`am-k8s-diagnostic-agent` and `am-vcf-diagnostic-agent`, in org `Goad`, space
`metal-music-app-agentic-system`. Each is tagged `agentminder-client` and
holds `client_id`, `client_secret` and `gateway_url`. The space is still the
platform engineer's: this root only reads it. The manifest binds each
service to its agent. `shared/sidecar/agentminder-env.sh` finds the bound
service tagged `agentminder-client` in `VCAP_SERVICES` and exports the
variables the SDK reads. The CF sidecar (`run-sidecar.sh`) and the web
process (`shared/trust/profile`) both source it. `tanzu-apps.yml` has no
AgentMinder values and reads no state. The three `INCIDENT_AM_*_CLIENT_SECRET`
GitHub secrets were deleted on 2026-10-28. A changed client secret reaches an app on
`cf restart <app>`.

Why Cloud Foundry services and not GitHub secrets written by Terraform:
writing a GitHub secret needs a PAT or a GitHub App key that can write
repository secrets, which `GITHUB_TOKEN` cannot. That is a new, powerful
credential, and `tanzu-apps` would still carry the values. With services the
secrets go from AgentMinder to Terraform to Cloud Foundry, and never through
GitHub or the push workflow. That is how `goad-qwen` and the `sc-*` services
already work.

Why `restapi` and not `terracurl`, which issue 38 named: terracurl keeps the
bearer token in state when it creates a resource and sends it again at
destroy. AgentMinder tokens expire, so a destroy months later fails. With
`restapi`, the token is new on every run, each object is read back so a change
in the console shows in the plan, and existing objects can be imported. The
token comes from an `http` data source rather than restapi's
`oauth_client_credentials`, because restapi 3.0.0's token request ignores
`insecure` and fails on the chart's self-signed certificate.

Why Terraform state and not Secret Store, for now: reading a
`KeyValueSecret` back needs an OpenBao login. The runner pods are in
`goad-runner`, a namespace vCenter made. They have no service account token,
and VCF Automation logins cannot write there. Gitea's state already holds
sensitive values.

**Never print the plan.** `restapi` keeps each response in attributes it
does not mark sensitive, and the response has the app's secret. A plan prints
the old value when it changes. So the workflow runs
`terraform plan -out=tfplan >/dev/null` and lists only each address and
action from `terraform show -json tfplan`. Do the same by hand, and do not
paste plan output anywhere.

**The import.** `imports.tf` finds the objects `register.py` made by name and
adopts them, so the running agents keep their IDs and secrets. The grants in
`AuthClientPolicy` are not imported: the first apply adds each client
again. Delete `imports.tf` after the first apply. On a new AgentMinder its
lookups find nothing and fail the plan.

Cost:
- The client secrets are in this root's state, in plain text, and in the
  services. Anyone with the Gitea state token or read access to the
  services can read them.
- `tanzu-apps` reads no state, but its push fails until the `am-*` services
  exist.
- A changed secret reaches an app only on `cf restart <app>`.

Look again if: AgentMinder gets service accounts, or the runner pods get a
way to log in to Secret Store. Move the login there.

## 42. The incident demo's tools run on a platform tools cluster, from gitops

Zammad, Grafana and Prometheus were applied by hand with
`incident-demo/apply.py` into namespace `incident-tools` of the music store
cluster, with hand-made Secrets. Now:

- **Their own cluster.** The platform engineer's Supervisor Namespace
  `platform-tools` holds the VKS cluster `platform-tools`
  (`gitops/platform-tools/`, the generic Application). The tools run in it,
  in namespace `incident-tools`, from `gitops/platform-tools-apps/`, which
  the Application `platform-tools-apps` syncs. The demo diagnoses a sick
  music store cluster, so the tools that record the incident must not go
  down with it, and other clusters can use them later.
- **Secrets from Secret Store.** Terraform writes the KVs
  `platform-tools-grafana`, `platform-tools-zammad` and `platform-tools-qwen`
  from GitHub secrets (`INCIDENT_GRAFANA_ADMIN_PASSWORD`,
  `INCIDENT_ZAMMAD_DB_PASSWORD`, `INCIDENT_ZAMMAD_ADMIN_PASSWORD`,
  `INCIDENT_QWEN_API_KEY`), and ESO makes `grafana-admin`, `zammad-env` and
  `qwen-probe`, as in decision 38. `zammad-env` is an ESO template: the two
  passwords come from the KV, the rest is in git.
- **Zammad keeps its data.** One Deployment per piece, with PVCs for
  Postgres and Zammad's storage. The bare Pods on `emptyDir` lost every
  ticket and the API token on a restart. Elasticsearch is gone: Zammad ran
  with `ELASTICSEARCH_ENABLED=false`, so it was never read.
- **Checks by the blackbox exporter.** The custom `probe.py` is replaced by
  `prom/blackbox-exporter`. Prometheus recording rules (`rules.yml`) turn its
  `probe_success` into the series the boards already read, `demo_up` and
  `arch_up`, so the boards did not change. Each probe target carries the
  board box (`id`) or tile (`check`) it feeds.
- **The music store's side.** The tools cluster cannot resolve the shop's
  in-cluster names. `gitops/music-store-platform/` adds a namespace
  `platform-tools` on the music store cluster with its own blackbox exporter
  and a Prometheus in agent mode, which probes those names, keeps the
  kube-state-metrics series the boards use, and remote-writes both to
  `prometheus.goad.gpu.set.lab`. The service account `goad-k8s-mcp`, which
  the Cloud Foundry app `metal-k8s-mcp` reads the cluster with, moves there
  too, with a token Secret that does not expire.
- **The architecture board is ported.** The topology panel lists what runs
  now: the MCP servers and pii-scrub as Cloud Foundry apps, Zammad in its
  own cluster, the music store's nodes as one box, and no addresses
  (decision 21). It still draws a fixed layout from `topology/module.js`.
- **Removed.** The earlier Kubernetes agents and MCP servers
  (`agents/`, `mcp/`, and their namespace `metal-music-app-agentic-system`
  on the music store cluster), CLM's manifest (no CLM image exists; the
  orchestrator falls back without it), `apply.py`, `BLANKS.md`,
  `RUNBOOK.md` and `secrets/templates.yaml`. The walk is
  `scripts/incident-walk.sh`. The second AgentMinder host name's Service is
  in `terraform/cloud-admin/agentminder`, imported. The runbook's lessons
  are in the tanzu README and the host name rules in `gitops/README.md`.
  `incident-demo/` is gone.
- **No address pins for Grafana and Zammad.** The incident apps resolve
  `*.goad.gpu.set.lab` through DNS (checked on 2026-10-28 with a task on
  `metal-incident-live`), so `manifest.yml` no longer pins their addresses,
  which change with the cluster.

Why gitops and not a script: the tools are long-lived services, not a step
a person takes. Decision 37 kept the incident demo out of `gitops/` because
a person ran it; that is now only the walk.

Why a Prometheus agent and remote write, not a scrape across clusters:
the shop's names resolve only inside its cluster, and the agent is the same
for any cluster added later. Why the blackbox exporter, not the custom
probe: it is maintained, it has nothing to keep in step with the lab, and
its targets are data.

Cost:
- One more VKS cluster: a best-effort-medium control plane and a
  best-effort-large worker.
- A new build starts Zammad empty. Someone makes its API token by hand and
  stores it as `INCIDENT_ZAMMAD_TOKEN` before `tanzu-apps` runs. Moving to
  this cluster was such a build.
- Prometheus's remote-write receiver and UI have no authentication. Anything
  on the lab network can write series to it.
- `INCIDENT_K8S_TOKEN` changed: it is the token from
  `platform-tools/goad-k8s-mcp-token`. The platform engineer workflow and
  `tanzu-apps` must run after it changes.
- The topology panel's layout is still hand-placed, and its node list must
  follow what runs.
- A rebuilt cluster keeps its old API address in its `ManagedEntity`, and
  Argo CD cannot reach it (`dial tcp <old address>:6443: i/o timeout`).
  Delete the `ManagedEntity` and run the platform engineer workflow, which
  makes it again. Seen on 2026-10-28, when `platform-tools` was rebuilt for
  `serviceDomain`.
- On a first install Zammad creates its admin user only when something
  calls `GET /api/v1/getting_started/auto_wizard`. That needs
  `AUTOWIZARD_RELATIVE_PATH` set and `tmp` shared between `zammad-init` and
  the Rails server; neither was so before 2026-10-28.

Look again if: VCF gives the tools a shared observability stack, or a second
tenant cluster needs Zammad and Grafana.

## 43. The shop is published through Gateway API, with a cert-manager certificate

The shop's Ingress `metal-store` is replaced by Gateway API, as Thomas
Kraus moved it on 2026-10-27: the Gateway `metal-store` in namespace
`default`, with HTTP and HTTPS listeners for `*.goad.gpu.set.lab`, the
HTTPRoute `metal-store-frontend` for `music.goad.gpu.set.lab`, and the
L7Rule `metal-store-waf`, which puts Avi's `System-WAF-Policy` on the route.
They are in `gitops/music-store-dev/app/` and in its kustomization, so Argo
CD applies them and prunes the Ingress. Before, the kustomization still
listed the deleted `ingress.yaml`, and the Application failed to build.

The HTTPS listener needs the Secret `default/https-goad.gpu.set.lab-cert`.
cert-manager makes it: the VKS cert-manager addon, installed on clusters
labelled `addons.kubernetes.vmware.com/cert-manager: enabled` by
`gitops/music-store/cert-manager.yaml`, and a self-signed `ClusterIssuer`
and wildcard `Certificate` in `gitops/music-store-platform/gateway-cert.yaml`.
No key is in git.

Why Gateway API: it is what AKO is moving to, and the WAF is attached with
an L7Rule, which only the Gateway API controller reads.

Cost: the certificate is self-signed, so browsers warn, as they did on
Avi's default certificate. The shop's address changed, so the incident
apps no longer pin it (`STORE_CONNECT_IP`); they resolve it.

Look again if: the lab gets a CA that cert-manager can issue from.

## 44. `app/music-store` is removed

`app/music-store/` held the shop's earlier shape: seven Deployments from the
published `ghcr.io/niranec77/metal-music-store-*` images, with a container
database and a container users service. Nothing deployed it. The shop that
runs is `gitops/music-store-dev/app` (its own manifests and source, because
Argo CD's kustomize does not load files from outside the directory it syncs),
with the users VM and the DSM catalog (decisions 21 and 34). The Antrea
policy test and `gateway-api/` that the README named had already moved out:
the Gateway API objects are in `gitops/music-store-dev/app` (decision 43).

Why: a second, unused copy of the shop invites edits that change nothing in
the lab, and its README described files that were no longer there.

Cost: the earlier manifests are only in git history, up to the commit before
this decision. That includes the traffic generator Deployment, which the
gitops shop does not have.

Look again if: the demo needs generated load on the shop. Bring the traffic
generator into `gitops/music-store-dev/app`.

## 45. The platform engineer deploys the music store; the developer writes its code

The developer's job is the shop's code, in `gitops/music-store-apps/src/`.
The developer does not deploy it. The platform engineer owns all of the
music store's deploy through Argo CD. With one owner, the split by owner
in decision 34 has no reason left, so the Applications are split by
destination:

- `music-store` syncs `gitops/music-store/` into the `music-store`
  Supervisor Namespace: the VKS cluster, the catalog, and now the users
  VM and the Job `shop-endpoints`. The files moved there from
  `gitops/music-store-dev/users-vm/`. The Application
  `music-store-dev-vm` is removed.
- `music-store-platform` syncs `gitops/music-store-platform/` into the
  VKS cluster, as before: the ESO store, the Gateway certificate, and
  what the platform tools cluster watches the shop with.
- `music-store-apps` syncs `gitops/music-store-apps/` into the namespace
  `music-store` of the VKS cluster: the shop's containers, its
  `ExternalSecret`s and its Gateway. The directory was
  `gitops/music-store-dev/app/`, and the Application was
  `music-store-dev-app`. The name matches `platform-tools-apps`.

`shop-endpoints` moves from wave 1 to wave 3. In one Application it runs
after the cluster (wave 0, which Argo CD holds until the Cluster is
healthy), the catalog's Endpoints (wave 1) and `catalog-init` (wave 2).
Waves replace the retry that the separate Application needed.

This changes three earlier decisions:

- Decision 34: the users VM and `shop-endpoints` are back in the
  Application `music-store`, and are the platform engineer's.
- Decision 37: still one owner and one Application for each directory.
  The developer owns `src/` inside `gitops/music-store-apps/`. That
  directory holds code, not deploy, and it stays there because Argo CD's
  kustomize does not load files from outside the directory it syncs.
- Decision 38: the platform engineer writes the `ExternalSecret`s
  `store-db` and `metal-oracle-model`. The developer tells the platform
  engineer which values the code reads.

Why: in the demo the developer builds the application and the platform
engineer runs it. Deploy, secrets and wiring are platform work.

Why the moves are safe in the lab: the Applications have no
`resources-finalizer.argocd.argoproj.io`, and Argo CD tracks resources by
annotation (`argocd-cm` `application.resourceTrackingMethod`, checked on
2026-10-28). Removing an Application leaves its resources running. The
Application that now holds the files applies them and writes its own
tracking annotation over the old one. Between the merge and the platform
engineer apply, the two old Applications show a comparison error for a
missing path and change nothing.

Cost: the developer still edits files inside a directory that Argo CD
syncs, so a code change is a deploy. The pods install their
requirements from PyPI and run the code on `python:3.12-slim` from Docker
Hub at every start.

Look again if: the lab gets a registry. Then the code moves out of
`gitops/`, CI builds images, and the platform engineer bumps the image
tag. Look again too if the developer gets a deploy of their own, for
example a `cf push` of the shop to Tanzu Platform.

## 46. Broadcom's content registry is proxied through the Supervisor's Harbor

The cloud admin's `terraform/cloud-admin/org` makes a proxy cache project,
`tanzu-platform-content`, in the Supervisor's Harbor (`harbor.tf`). It
proxies all of `tanzu-platform-content.packages.broadcom.com`, the
registry behind the Bitnami images Tanzu Hub lists, not one image. The
project is public: anything in the lab pulls without a login, by the
registry's own path with `10.47.7.12/tanzu-platform-content/` in front.

Why: Broadcom's registry needs a login for every pull. With the proxy,
only Harbor holds it, and the cloud admin owns it. Builds and clusters
need no Broadcom credential, and an image is fetched once and then served
from the lab. Inside VKS, the same project is
`depot.kube-system.svc/tanzu-platform-content/`: VKS nodes and pods
resolve and trust the Supervisor's Harbor by that name, not by its
address.

Why the cloud admin: the Broadcom entitlement and the Supervisor's Harbor
are provider scope, like the org's quota and networking. The platform
engineer's build pipeline consumes the project and does not manage it.

Why `docker-registry` as Harbor's registry type: Broadcom's registry is
Artifactory, but it serves the plain Docker Registry v2 API with bearer
tokens, which the generic type covers.

Cost: Harbor's admin password and the Broadcom token become cloud-admin
secrets (`HARBOR_ADMIN_PASSWORD`, `BROADCOM_REGISTRY_USERNAME`,
`BROADCOM_REGISTRY_TOKEN`). A Broadcom token expires, and an expired one
fails every pull Harbor has not cached yet. Anyone on the lab network can
pull Broadcom's entitled images from Harbor without a login.

Look again if: the lab gets a DNS name for Harbor, or the project has to
be private. Then the clusters and builds need a pull secret.

## 47. The cloud admin makes the music store's Harbor project and push login

`terraform/cloud-admin/org/harbor.tf` makes a public Harbor project,
`music-store`, and a project robot account, `robot$music-store+builder`,
that can only push and pull its repositories. The platform engineer's
build pushes the music store's images with it (issue #62), and the music
store's VKS cluster pulls them with no login.

Why the cloud admin: Harbor's admin login stays with the cloud admin, as
with the proxy cache in decision 46. The platform engineer gets a login
that reaches one project and nothing else.

Why a shared secret: the robot's secret is a team value in the GitHub
secret `MUSIC_STORE_HARBOR_ROBOT_SECRET`, set on the robot by Terraform
and read by the platform engineer's workflow, the same way the org
stages share `CLOUD_ADMIN_PASSWORD`. Terraform sets it write-only
(`secret_wo`), so it is never in state. Handing a generated secret to
the platform engineer would need a GitHub token with secret write access
in the cloud admin's workflow, a new credential for one value.

Why public: VKS trusts the Supervisor's Harbor already, so a public
project needs no pull secret and no CA in the cluster. The trust is for
the name the Supervisor registers Harbor under, `depot.kube-system.svc`
(its ClusterRegistryConfig and ClusterDomainResolutionEntry). A pull by
the address `10.47.7.12` fails with `x509: certificate signed by unknown
authority`, checked on the platform tools cluster on 2026-10-30. So images
in VKS are named `depot.kube-system.svc/music-store/<service>`.

Cost: Terraform cannot see the secret, so a change to it needs
`music_store_robot_secret_version` raised by one. Anyone on the lab
network can pull the music store's images.

## 48. The platform engineer builds the music store's images with Tekton

The developer writes the shop's code in `apps/music-store/<service>/` and
nothing else. The platform engineer owns everything from there to the
running shop, a golden path:

- The Dockerfile: one template for a Python service,
  `gitops/platform-tools-builds/dockerfiles/python`, `FROM` Bitnami's
  Python on Photon 5 through the Harbor proxy cache (decision 46). Every
  service is built from it, with its own directory as the context.
- The build: Tekton, from the VKS addon `tekton-operator`, on the
  platform tools cluster. The Pipeline `music-store-images` clones one
  commit with the read-only deploy key, then builds the four images with
  BuildKit and pushes them as `robot$music-store+builder`
  (decision 47), tagged with the commit.
- The trigger: the workflow `music-store-images.yml`, on a push to main
  that changes `apps/music-store/`. It starts a PipelineRun as the
  ServiceAccount `pipeline-starter`, waits, and shows the result and the
  logs in GitHub.
- The deploy: the workflow then opens a pull request that sets the new
  tag in `gitops/music-store-apps/kustomization.yaml`. Merging it is the
  deploy. Building is not deploying.

Why Tekton on a VKS cluster: the runner is a vSphere Pod with no
capabilities and no Docker daemon, so it cannot build. GitHub's own
runners cannot reach Harbor. Tekton comes with VKS as an addon, and the
platform tools cluster is already the platform engineer's.

Why the workflow starts the build: GitHub cannot reach the lab, so a
webhook is not possible, and a PipelineRun started from the workflow
reports back to GitHub. Tekton Triggers would need an exposed listener
and would leave GitHub blind to the result.

Why BuildKit runs privileged: rootless BuildKit needs unprivileged user
namespaces, which the Ubuntu 24.04 nodes restrict. The namespace
`music-store-builds` is Pod Security privileged for it, and holds nothing
else.

Cost: `pipeline-starter`'s token is a long-lived ServiceAccount token, in
the GitHub secret `MUSIC_STORE_BUILD_KUBECONFIG`
(`scripts/music-store-build-kubeconfig.sh`). It can only start and read
PipelineRuns in one namespace. The workflow's pull request needs the
repository setting that lets GitHub Actions create pull requests. The
deploy key now also reaches the platform tools cluster.

Look again if: the runner gets a way to build itself, or Tekton gets a
listener the lab can reach.

Update, 2026-10-30: the shop runs from the images. The first build was
`ff4cf83e2310`. `gitops/music-store-apps/src/` and `covers/` are removed,
and `kustomization.yaml` sets the tag in `images:`. Decision 45's cost,
a code change being a deploy and a `pip install` at every start, is gone.

