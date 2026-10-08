# Terraform state

Where the state of the two Terraform roots lives, how to set up a
machine to use it, and how it was set up in Gitea.

## Where it is

The lab's Gitea server has a Terraform state registry. Terraform's `http`
backend talks to it. Gitea stores the state, locks it during a run, and
keeps every version.

| Root | Gitea organization | State name |
|---|---|---|
| `terraform/cloud-admin` | `the-goad` | `goad-cloud-admin` |
| `terraform/platform-engineer` | `the-goad` | `goad-platform-engineer` |

In Gitea, the states are under the organization's Packages.

## The files on your machine

None of these are in git. Each has an `.example` beside it that is.

| File | Read at | Holds | Same for everyone |
|---|---|---|---|
| `backend.hcl` | `terraform init` | Where the state is, and the shared token | Yes |
| `terraform.tfvars` | `terraform plan` and `apply` | Lab values and your passwords | No |
| `.secrets/gitops-deploy-key` | `terraform apply` | Argo CD's deploy key (platform engineer only) | Yes |

The token cannot go in `terraform.tfvars`. Terraform reads the backend
settings before it reads any variable, so a `backend` block cannot use
one. `backend.tf` is empty for that reason, and the settings come from
`backend.hcl` at `init`.

## Set up a machine

In each root:

```sh
cp backend.hcl.example backend.hcl
```

Fill in `backend.hcl`:

- `GITEA-HOST`: the lab git server.
- `OWNER`: `the-goad`.
- `password`: the token of the Gitea user `goad-terraform`. Get it from
  a teammate, through a password manager or a direct message. Never
  through git or email.
- Remove the `#` from `skip_cert_verification = true`. The lab git
  server has a self-signed certificate.

```sh
chmod 600 backend.hcl
terraform init -backend-config=backend.hcl
terraform plan
```

The plan shows no changes if nobody is in the middle of one.

After `init`, Terraform also keeps the backend settings, token included,
in `.terraform/terraform.tfstate` in that root. Git ignores `.terraform/`
too.

## What the state holds

Passwords and a private key: the VCF Automation provider administrator
password, the org administrator password, the Argo CD deploy key, and
the Private AI Services password hash. Anyone with the shared token can
read them. Treat the token as you would those.

## How it was set up in Gitea

Once, by a Gitea administrator. Nothing has to be enabled on the server:
the package registry is on by default, and the state is created at the
first `terraform init` that migrates or writes one.

1. Create the organization `the-goad`.
2. Create the user `goad-terraform`.
3. In the organization, create a team with the **Packages** unit set to
   **Write**, and add `goad-terraform` to it. Being a member of the
   organization is not enough.
4. As `goad-terraform`, create an access token with the permission
   **package: Read and Write** and nothing else.

## When it goes wrong

| What Terraform says | Cause | Fix |
|---|---|---|
| `Backend initialization required` | No `terraform init` on this machine since the backend was added | `terraform init -backend-config=backend.hcl` |
| `HTTP remote state endpoint requires auth`, at the lock | Gitea answered `401 reqPackageAccess`. Wrong token, or the user's team does not have Packages set to Write. Reading can still work in the second case. | Check the token. Then check the team. |
| `Error acquiring the state lock`, with a lock ID | Someone is applying, or a run was killed and left its lock | Wait. If the run is dead: `terraform force-unlock <ID>` |
| A certificate error | `skip_cert_verification` is not set | Set it in `backend.hcl` and run `init` again |

To check the token without Terraform:

```sh
curl -sk -o /dev/null -w '%{http_code}\n' -u goad-terraform:TOKEN \
  https://GITEA-HOST/api/packages/the-goad/terraform/state/goad-cloud-admin
```

`200` is good. `401` is a wrong token. A `404` means the token is
accepted and that state does not exist.

## Going back to an earlier state

Gitea keeps each version under its serial number.

```sh
# The current state. Its "serial" is the newest version.
curl -sk -u goad-terraform:TOKEN https://GITEA-HOST/api/packages/the-goad/terraform/state/NAME

# An earlier one
curl -sk -u goad-terraform:TOKEN https://GITEA-HOST/api/packages/the-goad/terraform/state/NAME/versions/SERIAL \
  -o earlier.tfstate
```

To put an earlier one back, raise the `serial` in the file above the
current one and run `terraform state push earlier.tfstate`. Do this only
when you know why the current state is wrong.

## Replacing the token

Create a new token for `goad-terraform` in Gitea and delete the old one.
Everyone puts the new one in both `backend.hcl` files and runs
`terraform init -reconfigure -backend-config=backend.hcl`.

The reasons for this backend are in [decisions.md](decisions.md), number
21.
