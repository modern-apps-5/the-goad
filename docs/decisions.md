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
Engine quota. The platform engineer creates the org's Service Engine
Group.

Why: that is how the lab region already runs, and it puts sizing with
the persona that owns the workloads. A Supervisor Namespace that names
a group is refused until both exist.

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
`app/music-store` as the earlier shape. `kustomization.yml` still lists
them. Argo CD syncs `gitops/music-store/`, not that directory.

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
