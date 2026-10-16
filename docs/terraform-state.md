# Terraform state

Where the state of the Terraform roots lives, how to set up a
machine to use it, and how it was set up in Gitea.

## Where it is

The lab's Gitea server has a Terraform state registry. Terraform's `http`
backend talks to it. Gitea stores the state, locks it during a run, and
keeps every version.

| Root | Gitea organization | State name |
|---|---|---|
| `terraform/cloud-admin/org` | `the-goad` | `goad-cloud-admin` |
| `terraform/cloud-admin/org-config` | `the-goad` | `goad-cloud-admin-org-config` |
| `terraform/cloud-admin/agentminder` | `the-goad` | `goad-cloud-admin-agentminder` |
| `terraform/platform-engineer` | `the-goad` | `goad-platform-engineer` |
| `terraform/runner` | `the-goad` | `goad-runner` |

In Gitea, the states are under the organization's Packages.

## The files on your machine

| File | In git | Read at | Holds |
|---|---|---|---|
| `lab.auto.tfvars` | yes | `terraform plan` and `apply` | Every lab value that is not secret |
| `backend.tf` | yes | `terraform init` | Where the state is, how to lock it, and the shared user's name |
| `backend.hcl` | no | `terraform init` | The shared user's token, and nothing else |
| `terraform.tfvars` | no | `terraform plan` and `apply` | The passwords of the shared accounts, and the password hash |
| `.secrets/gitops-deploy-key` | no | `terraform apply` | Argo CD's deploy key (platform engineer only) |
| `.secrets/private-key.pem` | no | `terraform apply` | The GitHub App's private key (runner only) |

Those that are not in git each have an `.example` beside them that is,
or for the two keys, instructions in `terraform.tfvars.example`.

Lab values are in git so that they cannot differ between people. Only
what is secret has to be passed around.

`terraform/cloud-admin/agentminder` also reads the state of `org-config`
with `terraform_remote_state`. A data source cannot read `backend.hcl`,
so on a machine also `export TF_HTTP_PASSWORD=<the same token>` before
`plan` and `apply`. The workflow sets it.

The token cannot go in `terraform.tfvars`. Terraform reads the backend
settings before it reads any variable, so a `backend` block cannot use
one. So `backend.tf` holds everything about the backend that is not
secret, and the token alone comes from `backend.hcl` at `init`.

## Everyone must use the same values

The state is shared, and Terraform makes the lab match the inputs of
whoever applies. If your inputs differ from a teammate's, your apply
changes what theirs set, and their next apply changes it back.

So these are team files, not personal ones. Get them from a teammate
and do not make your own.

| Value | Where | If yours differs |
|---|---|---|
| Deploy key | `terraform/platform-engineer/.secrets/gitops-deploy-key` | Terraform replaces the key in Argo CD's repository Secret with yours. Yours is not on the GitHub repository, so Argo CD can no longer read git and stops syncing. |
| `pais_admin_password_hash` | `terraform/platform-engineer/terraform.tfvars` | The hash is salted. A new hash of the same password is still a different value, so Terraform rewrites the Secret and Private AI Services restarts pods. Copy the hash itself. |
| `cloud_admin_password` | `terraform/cloud-admin/org/terraform.tfvars`, `terraform/cloud-admin/org-config/terraform.tfvars`, and `terraform/cloud-admin/agentminder/terraform.tfvars` | Terraform changes the password of `cloud-admin`, the org's one local user. Stage 2 and everyone else's login then fail. It is the same value in all three files. |
| `ssp_registry_username` and `ssp_registry_password` | `terraform/cloud-admin/agentminder/terraform.tfvars` | Not written to the lab, but a wrong one fails the image pulls from Broadcom's registry. Terraform does write them into the Secret `ssp-registry`. |
| `ops_password` | `terraform/cloud-admin/org/terraform.tfvars` | Not written to the lab, but a wrong one fails the VCF Operations login that makes the org's VCF SSO client. |
| `vcfa_api_token` | `terraform/platform-engineer/terraform.tfvars` | Not written to the lab, but a wrong one fails the login. It is an API token of `svc.platform_engineer@set.lab`, made by hand once. |
| `vcfa_password` | `terraform/cloud-admin/org/terraform.tfvars` | Not written to the lab, but a wrong one fails the login. It is the provider administrator's password. |
| `vcenter_password` | `terraform/runner/terraform.tfvars` | Not written to the lab, but a wrong one fails the login. |
| GitHub App's private key | `terraform/runner/.secrets/private-key.pem` | Terraform replaces the key in the Secret `github-app` with yours. If yours is not a key of that App, the runner's pods cannot register after their next restart. |

The repository secrets in GitHub are one more copy of these values
and of the state token. The workflows apply with them. When one
of these values changes, change the repository secret too:
[terraform/runner/README.md](../terraform/runner/README.md) lists which
secret holds which value.

Quota, VM classes, zone, and policy names are not on this list any more.
They are in `lab.auto.tfvars`, in git, so everyone has the same ones. To
change one, change that file and commit it; the change is then reviewed
like any other.

The simplest rule: keep one copy of each of these in the team's password
manager, and copy the whole file.

- `terraform/cloud-admin/org/terraform.tfvars` (three passwords)
- `terraform/cloud-admin/org-config/terraform.tfvars` (one password)
- `terraform/cloud-admin/agentminder/terraform.tfvars` (the same password,
  and the registry login)
- `terraform/platform-engineer/terraform.tfvars` (one API token, one
  hash)
- `terraform/platform-engineer/.secrets/gitops-deploy-key`
- The token for `backend.hcl`

Before you apply, run `terraform plan`. With the shared files it shows
no changes, or only the change you mean to make. If it shows a change to
`gitops_repository`, `pais_static_credentials`, or `vcfa_org_local_user`
that you did not intend, your files differ. Stop and compare them.

### The deploy key

It is one key pair. The public half is on the GitHub repository, under
Settings, Deploy keys, as `goad-argocd-read`, read-only. The private half
is the file above. Terraform puts it in the Secret `gitops-repo` in the
`platform` namespace, and Argo CD uses it to read this repository.

Make a new key pair only when you mean to replace it for everyone: add
the new public half to the repository, give the new private half to the
team, apply, then delete the old deploy key on GitHub.

## Set up a machine

In each root:

```sh
cp backend.hcl.example backend.hcl
chmod 600 backend.hcl
```

Put the token of the Gitea user `goad-terraform` in `backend.hcl`. It is
the only line. Get the token from a teammate, through a password manager
or a direct message. Never through git or email.

Then get the shared `terraform.tfvars` files and the deploy key the same
way: see "Everyone must use the same values" above.

```sh
terraform init -backend-config=backend.hcl
terraform plan
```

The plan shows no changes if nobody is in the middle of one.

After `init`, Terraform also keeps the backend settings, token included,
in `.terraform/terraform.tfstate` in that root. Git ignores `.terraform/`
too.

## What the state holds

Passwords, a token, and a private key: the VCF Automation provider
administrator password, the `cloud-admin` password, the VCF Operations
password, the platform engineer's API token, the Argo CD deploy key, and
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
| A certificate error | `skip_cert_verification` is not set | It is set in `backend.tf`. Pull, and run `init` again. |

To check the token without Terraform:

```sh
curl -sk -o /dev/null -w '%{http_code}\n' -u goad-terraform:TOKEN \
  https://git.gpu.set.lab/api/packages/the-goad/terraform/state/goad-cloud-admin
```

`200` is good. `401` is a wrong token. A `404` means the token is
accepted and that state does not exist.

## Going back to an earlier state

Gitea keeps each version under its serial number.

```sh
# The current state. Its "serial" is the newest version.
curl -sk -u goad-terraform:TOKEN https://git.gpu.set.lab/api/packages/the-goad/terraform/state/NAME

# An earlier one
curl -sk -u goad-terraform:TOKEN https://git.gpu.set.lab/api/packages/the-goad/terraform/state/NAME/versions/SERIAL \
  -o earlier.tfstate
```

To put an earlier one back, raise the `serial` in the file above the
current one and run `terraform state push earlier.tfstate`. Do this only
when you know why the current state is wrong.

## Replacing the token

Create a new token for `goad-terraform` in Gitea and delete the old one.
Everyone puts the new one in every `backend.hcl` file and runs
`terraform init -reconfigure -backend-config=backend.hcl`.

## Pointing at another Gitea, organization, or state name

Change `backend.tf` and commit it. Everyone then runs
`terraform init -reconfigure -backend-config=backend.hcl`. Changing the
address does not move the state: copy it first with
`terraform init -migrate-state`.

The reasons for this backend are in [decisions.md](decisions.md), number
22.
