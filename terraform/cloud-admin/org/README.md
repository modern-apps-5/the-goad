# Cloud admin foundation, stage 1: the org

The cloud admin's Day 0 Terraform, first of three roots. It runs against the VCF Automation
provider (System) org and stops at the tenant boundary. Stage 2, [../org-config](../org-config),
configures things inside the org and runs after this one. Stage 3, [../agentminder](../agentminder), installs AgentMinder. The agentic
ops engineer registers the incident demo's agents in it, in
[../../agentic-ops](../../agentic-ops). The state is
`goad-cloud-admin`.

The region, its Distributed VLAN Connection, and the IP space already
exist in the lab. This root starts at the org and attaches it to them.

| File | What it creates |
|---|---|
| `existing.tf` | Nothing. Reads the existing region and Distributed VLAN Connection. |
| `org.tf` | The org and its one local user, `cloud-admin`, an Organization Administrator. |
| `quota.tf` | The org's region quota: CPU and memory per zone, VM classes, storage. |
| `networking.tf` | The org's networking settings, its connection to the Distributed VLAN Connection, and the Avi load balancer setting. |
| `dsm.tf` | The org's DSM data service policy for PostgreSQL. Skipped until `dsm_infrastructure_policy_names` is set. |
| `harbor.tf` | In the Supervisor's Harbor: a public proxy cache project, `tanzu-platform-content`, for Broadcom's Tanzu Platform content registry, and a public project, `music-store`, with the robot account `robot$music-store+builder` that the platform engineer pushes the music store's images with. |
| `oidc.tf` | VCF SSO for the org: its OIDC client in the VCF Identity Broker, then the org's OIDC setting. Skipped when `vcf_sso` is false. |

The outputs are what the platform engineer needs: the org to log in to,
and the region, zones, VM classes, and storage policies to place
Supervisor Namespaces in.

## Apply

```sh
cp terraform.tfvars.example terraform.tfvars   # secrets only; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

This root used to be `terraform/cloud-admin`. If you have the old one,
move your ignored `backend.hcl` and `terraform.tfvars` into `org/` and run
`terraform init -backend-config=backend.hcl` there again.

The secrets in `terraform.tfvars`: `vcfa_password` (provider
administrator), `cloud_admin_password` (the team's shared password for
`cloud-admin`), `ops_password` (VCF Operations administrator),
`harbor_admin_password` (the Supervisor's Harbor administrator), and
`broadcom_registry_username` and `broadcom_registry_token` (a Broadcom
registry token for the Harbor proxy cache), and `music_store_robot_secret`
(the secret of the music store's Harbor robot account). The
inputs for VCF SSO are `ops_url`, `vidb_hostname`, and `vcf_sso`
(default `true`). `cloud_admin_username` defaults to `cloud-admin`.

## Regional networking uses TerraCurl

`vcfa_org_regional_networking` in provider 1.2.x only accepts a provider
gateway. The lab region has no provider gateway. It uses a Distributed
VLAN Connection, so `networking.tf` calls
`/cloudapi/vcf/regionalNetworkingSettings` with the `terracurl` provider.

- One resource sends the create call. A second reads the new setting
  and deletes it on destroy.
- Apply does not wait for the setting to be realized. That takes from a
  few seconds to a few minutes. A `check` block warns while it is not
  realized; run `terraform plan` again to see it pass. Supervisor
  Namespaces cannot be created in the org before then.
- `providers.tf` logs in on every run and gives TerraCurl the session
  token. The token is in state, and it expires.
- Terraform does not detect drift on this one object.

Replace these resources with `vcfa_org_regional_networking` when the
provider supports the connection.

## The DSM policy uses the kubernetes provider

A data service policy lives in DSM, not in VCF Automation. DSM serves a
Kubernetes API, and VCF Automation proxies it at
`/proxy/external-endpoint/api/dsm/regions/<region>/` with the same
provider token. Terraform does not need a route to the DSM appliance.

`dsm.tf` manages one `DataServicePolicy` as a `kubernetes_manifest`. It
matches the org by ID and allows PostgreSQL on the listed DSM
infrastructure policies. Every namespace of the org then sees it in its
`DataServicePolicyBinding`. Unlike the TerraCurl objects, Terraform
detects drift on this one.

## VCF SSO uses VCF Operations' internal API

An org can have only one local user, so everyone else signs in with VCF
SSO: their AD account, through the VCF Identity Broker (`vidb_hostname`).
The org needs an OIDC client in the broker. No provider can create one,
and the documented broker API needs a client token of a tenant
administrator. The portal makes it in VCF Operations.

`oidc.tf` logs in to VCF Operations and creates the client with the
`terracurl` provider at `/suite-api/internal/vidb/oauthclients`, with the
header `X-vRealizeOps-API-use-unsupported`. Then it sets `vcfa_org_oidc`
with that client.

The API is internal and unsupported. It can change in another release.
If it does, `oidc.tf` fails and needs a fix.

## Before the first apply

- Login is user and password. An API token session cannot create the
  org's local user: VCF Automation answers
  `ACCESS_TO_RESOURCE_IS_FORBIDDEN`.
- State holds the `cloud-admin` password and the OIDC client secret.
  State is remote: see "Terraform state" in the top-level
  README.

## Not covered

- GPU. No GPU VM class is in the example quota. Add the class name to
  `vm_class_names` when a GPU is allocated.
- OIDC group to role mapping. The provider has no resource to import
  an OIDC group and give it a role. Stage 2 imports the platform engineer
  group with the VCF Automation API instead (decision 36).
