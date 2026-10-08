# Cloud admin foundation

The cloud admin's Day 0 Terraform. It runs against the VCF Automation
provider (System) org and stops at the tenant boundary.

The region, its Distributed VLAN Connection, and the IP space already
exist in the lab. This root starts at the org and attaches it to them.

| File | What it creates |
|---|---|
| `existing.tf` | Nothing. Reads the existing region and Distributed VLAN Connection. |
| `org.tf` | The org and its first organization administrator. |
| `quota.tf` | The org's region quota: CPU and memory per zone, VM classes, storage. |
| `networking.tf` | The org's networking settings and its connection to the Distributed VLAN Connection. |
| `oidc.tf` | The org's OIDC identity provider. Skipped until `oidc` is set. |

The outputs are what the platform engineer needs: the org to log in to,
and the region, zones, VM classes, and storage policies to place
Supervisor Namespaces in.

## Apply

```sh
cp terraform.tfvars.example terraform.tfvars   # then fill in
terraform init
terraform plan
terraform apply
```

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

## Before the first apply

- Login is user and password. An API token session cannot create the
  organization administrator: VCF Automation answers
  `ACCESS_TO_RESOURCE_IS_FORBIDDEN`.
- State holds the organization administrator password and the OIDC
  client secret. This root uses local state, and `.gitignore` keeps it
  out of the repository. Choose a backend before more than one person
  applies.

## Not covered

- GPU. No GPU VM class is in the example quota. Add the class name to
  `vm_class_names` when a GPU is allocated.
- OIDC group to role mapping. The provider configures the identity
  provider for the org but has no resource to import an OIDC group and
  give it a role. That step is manual in the UI until it is automated
  another way.
