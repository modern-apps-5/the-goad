# Decisions

Choices made while building this repository, and why. Each one lists
what would make it worth a second look. Newest last.

Lab facts these rest on: VCF Automation 9.1.1, one region backed by one
Supervisor, a Distributed Transit Gateway with a Distributed VLAN
Connection for external traffic, Avi as the load balancer, and the
`vmware/vcfa` Terraform provider 1.2.3.

## 1. The cloud admin Terraform starts at the org

The region, its Distributed VLAN Connection, and the IP space already
exist in the lab. `terraform/cloud-admin` reads them and creates the org
and what belongs to it.

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
`ACCESS_TO_RESOURCE_IS_FORBIDDEN`, and `org.tf` creates the org's first
administrator.

Why: one credential that can do everything in the root.

Look again if: the first administrator comes from an identity provider
and the local user goes away.

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

## 16. Secrets and state stay local

Passwords and keys are in `terraform.tfvars` and `.secrets/`, both
ignored by git. State is local and ignored too. State holds secrets.

Look again when: a second person needs to apply. Choose a backend then.

## 17. Terraform resources have descriptive names

Not `this`. A rename of a resource that is already in state gets a
`moved` block. `terraform/cloud-admin` still has resources named `this`.

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

## 19. The database address is written into git after the database exists

`PAISConfiguration` takes the database host as a plain string. DSM
assigns the address when it creates the database. So `pais.yaml` holds
the address, and it was committed after `postgres.yaml` had been synced.

Why: it keeps Private AI Services in git with no extra machinery.

Cost: a rebuild from nothing needs two commits, and the address in git
is wrong until the second one.

Look again if: the demo is rebuilt often. Then give the database a DNS
name, or have Terraform read the address.

## 20. Terraform creates the Private AI Services login Secret

`pais-static-credentials` holds a password hash. Terraform creates it in
the `private-ai` namespace from `terraform.tfvars`. Argo CD does not
manage it.

Why: a hash does not belong in git, and one Secret does not justify a
secrets manager.

