# Cloud admin, stage 2: inside the org

The cloud admin's second Terraform root. It logs in to the org that
[../org](../org) created, as the org's one local user `cloud-admin`, and
configures things inside it. Apply `terraform/cloud-admin/org` first. The
state is `goad-cloud-admin-org-config`.

| File | What it creates |
|---|---|
| `users.tf` | The VCF SSO users in the org, and what they may do. |

## Users

VCF SSO users are AD accounts that sign in through the VCF Identity
Broker. A user does not exist in the org until it is imported.
`users.tf` imports them with `POST /cloudapi/1.0.0/users` and
`providerType` `OAUTH`.

- Platform engineers (`platform_engineers`) get the org role
  Organization User. A ProjectRoleBinding
  (`authorization.cci.vmware.com/v1alpha1`, named
  `cci:user:<domain>:<user>`, applied server side) makes each of them
  admin of the project `platform_engineer_project`, which is
  `default-project`.
- The AD service account `platform_engineer_automation_user`
  (`svc.platform_engineer@set.lab`) is imported as Organization
  Administrator. It is the platform engineer's automation login:
  `terraform/platform-engineer` uses an API token of this user.

A new AD user can log in only after the Identity Broker syncs the
directory (VCF Operations, Fleet Management, Identity & Access, VCF SSO).

## Apply

```sh
cp terraform.tfvars.example terraform.tfvars   # secrets only; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

## Inputs

- `lab.auto.tfvars`, in git: `vcfa_url`, `allow_unverified_ssl`,
  `platform_engineers`, and `platform_engineer_automation_user`.
  `org_name` (default `goad`), `cloud_admin_username` (default
  `cloud-admin`), and `platform_engineer_project` (default
  `default-project`) have defaults.
- `terraform.tfvars`, not in git: `cloud_admin_password`. It is the same
  value as in `terraform/cloud-admin/org`. Copy the team's file.

Login is user and password, as `cloud-admin`. State is remote: see
"Terraform state" in the top-level README.
