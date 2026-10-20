# Cloud admin, stage 2: inside the org

The cloud admin's second Terraform root. It logs in to the org that
[../org](../org) created, as the org's one local user `cloud-admin`, and
configures things inside it. Apply `terraform/cloud-admin/org` first. The
state is `goad-cloud-admin-org-config`.

| File | What it creates |
|---|---|
| `users.tf` | The VCF SSO users in the org, and what they may do. |
| `avi.tf` | The org's Avi Service Engine Group. |
| `agentminder.tf` | The project `cloud-admin`, the AgentMinder Supervisor Namespace, and the VKS cluster `agentminder`. |
| `kro.tf` | The project `kro-authors`, the role of the platform engineer group in it, and a small Supervisor Namespace. |
| `outputs.tf` | The names that `terraform/cloud-admin/agentminder` reads. |

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

## Avi

`avi.tf` creates the Service Engine Group `goad-se-group`: two 1-vCPU,
2 GB Service Engines shared by all virtual services. Every load balancer
in the org runs on them.

The platform engineer used to create it. It is here now because the
AgentMinder namespace below names it, and this root runs first.
`terraform/platform-engineer` only names it.

The group moved here from the platform engineer's state with a one-shot
`import` block and `removed` blocks, applied once in the lab and then
deleted from the code. [Decision 6](../../../docs/decisions.md) has the reason.

## AgentMinder

`agentminder.tf` makes what AgentMinder runs on. AgentMinder itself is
[../agentminder](../agentminder).

- The project `cloud_admin_project` (`cloud-admin`), applied with
  `kubectl_manifest` on the org API. It uses `server_side_apply`: the API
  refuses the last-applied annotation of a client-side apply, with "Only
  project spec can be updated". Platform engineers have no role in it.
- A Supervisor Namespace `agentminder-xxxxx` in that project. It names the
  Service Engine Group.
- The VKS cluster `agentminder` (`vcfa_vks_cluster`): one control plane
  (`best-effort-medium`) and two workers (`best-effort-large`), cluster
  class `builtin-generic-v3.7.0`, Kubernetes `v1.36.2+vmware.2`. The
  workers have a 50Gi volume for containerd, because AgentMinder's
  images fill the node's own disk.

The outputs are `cloud_admin_project`, `agentminder_namespace`, and
`agentminder_cluster_name`.

## kro

`kro.tf` makes the project where platform engineers author kro APIs. The
kro Supervisor Service lets editors and admins of a listed project create
ResourceGraphDefinitions (RGDs) in the org's API group, here
`goad.kro.run`. [Decision 35](../../../docs/decisions.md) has the reason.

- The project `kro_authors_project` (`kro-authors`), applied with
  `kubectl_manifest` and `server_side_apply`, like the cloud-admin project.
- A ProjectRoleBinding named `cci:group:set.lab:ans-platform-engineer`
  gives the VCF SSO group `kro_author_group` the project role `edit`.
  VCF Automation requires the name `cci:group:<domain>:<group>`. The group
  must already be in the org: it is imported by hand, and nothing in
  Terraform imports it. The role `edit` is enough to author, because VCF
  Automation sends the same `edit-<project>` group to the Supervisor for
  edit and admin.
- A Supervisor Namespace `kro-authors-xxxxx` (class small, 2000M CPU, 4Gi
  memory, 10Gi storage). It is only there so authors have a kubectl context
  in the project. RGDs are cluster-scoped and use no quota. Instances of
  `goad.kro.run` kinds go in the org's other namespaces.

The automation user `svc.platform_engineer@set.lab` is an Organization
Administrator, so it already counts as an editor of every project. Argo CD
reaches the Supervisor as that user, so it can sync RGDs pointed at the
kro-authors namespace.

The service and its values are set on the Supervisor by the vSphere admin,
not by this repo. The values list the project by its uid. Get it for the
admin with:

```sh
kubectl --context <org context> get project kro-authors -o jsonpath='{.metadata.uid}'
```

If the project is deleted and recreated, it gets a new uid, and authors are
refused until the values are updated.

The outputs are `kro_authors_project` and `kro_authors_namespace`.

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
- `lab.auto.tfvars` also holds what `terraform/cloud-admin/org` gave the
  org: `region_name`, `zone_name`, `vpc_name`, and `storage_class_name`.
  `service_engine_group_name` (default `goad-se-group`),
  `cloud_admin_project` (default `cloud-admin`), and
  `agentminder_cluster` (name, version, cluster class, VM classes, worker
  count, containerd disk) have defaults. The VM classes must be among
  the org's.
- `lab.auto.tfvars` also holds `kro_author_group`
  (`ans-platform-engineer@set.lab`), the VCF SSO group that authors kro
  RGDs. `kro_authors_project` (default `kro-authors`) has a default.
- `terraform.tfvars`, not in git: `cloud_admin_password`. It is the same
  value as in `terraform/cloud-admin/org`. Copy the team's file.

Login is user and password, as `cloud-admin`. State is remote: see
"Terraform state" in the top-level README.
