# Security admin: vDefend guardrails

The security admin's Terraform. It writes layer 1 of the music store's
network policy in NSX Manager, as vDefend rules, and NSX pushes them into
the VKS cluster `music-store` as Antrea ClusterNetworkPolicies through the
cluster's Antrea NSX integration (decision 49). It also writes the
vDefend Distributed IDPS policy for the users VM (decision 52).

| File | What it creates |
|---|---|
| `services.tf` | The ports the security admin's rules name. Today only the store's front end, TCP 5000. |
| `groups.tf` | One Antrea group per shop service (`store`, `cart`, `order`, `chat`), matched on the pod labels `app-name`, `env` and `service-name`. |
| `policy.tf` | The parent security policy `music-store` in the Application category, its tie to the cluster's container cluster, and the rule `frontend-from-avi`. |
| `idps.tf` | The IDPS policy for the users VM `music-users`, in the goad org's NSX project `goad`: a group, a profile, a policy and the rule `users-vm-inbound`. |

## The three layers

Antrea evaluates every policy in one pipeline, lowest tier first. The
first matching rule decides.

```
 vDefend tiers, NSX-managed, read-only in the cluster
   0  nsx-category-ethernet
   1  nsx-category-emergency
   2  nsx-category-infrastructure
   3  nsx-category-environment
   4  nsx-category-application   <-- layer 1, security admin (this root)
 Native Antrea tiers
  50  emergency
 100  securityops
 150  networkops
 200  platform
 250  application                <-- layer 2, developer (gitops/music-store-apps)
 Kubernetes NetworkPolicy
 253  baseline                   <-- layer 3, platform engineer (gitops/music-store-platform)
```

Rules for this layer:

- Allow rules only. A catch-all drop at tier 4 would decide every flow
  before the developer's tier 250, so their rules could never allow
  anything.
- Use a drop only for true guardrails, such as quarantine or environment
  isolation, in the Emergency or Environment categories.
- A vDefend allow is final: the developer cannot tighten it. Mandate only
  what the security admin must own.
- Do not use `JUMP_TO_APPLICATION`. In Antrea that is `Pass`, which skips
  every remaining Antrea tier, the developer's included.
- Never edit the pushed policy with `kubectl`. The ccp-adapter puts it
  back. Change it here.

## IDPS for the users VM

`idps.tf` protects the users VM, which Antrea policy does not reach. All
objects are in the NSX project `goad`.

- Group `music-users`: the SegmentPort tag `app|users-service`. VM
  Operator copies it from the VM label in
  `gitops/music-store/users-vm.yaml`, so the group follows the VM, not
  its IP or name.
- Profile `music-users`: severities critical, high and medium, with the
  six CVE-2021-41773 and CVE-2021-42013 signatures set to reject.
- Policy `music-users`, category ThreatRules, with the rule
  `users-vm-inbound`.

Terraform keeps the rule in DETECT. Matches are logged and traffic is
not stopped. The demo `demos/vdefend-virtual-patching` flips the rule to
DETECT_PREVENT through the NSX API, so it is fast on stage. That is
drift: the next apply of this root puts the rule back to DETECT.

The policy needs IDPS turned on for the vSphere cluster. The plan stops
with an error if it is off. That switch covers the whole cluster, so it
is a lab prerequisite and not in this Terraform: see
[docs/build.md](../../docs/build.md). IDPS sees traffic on VM vNICs
only. It does not see pod to pod traffic inside a VKS node or in the
tunnel between nodes.

## Apply

The cluster must be up with Antrea's NSX integration on
(`gitops/music-store/antrea-nsx.yaml`), so NSX has a container cluster
to tie the policy to. The root finds it by name pattern, because the
Supervisor Namespace's name has a generated suffix.

The workflow `security-admin.yml` runs this root: Actions, security-admin,
Run workflow. It plans, and applies only when `apply` is ticked, on
`main`. The NSX password is the GitHub secret
`SECURITY_ADMIN_NSX_PASSWORD`.

By hand:

```bash
cp backend.hcl.example backend.hcl          # the Gitea token
cp terraform.tfvars.example terraform.tfvars # the NSX password
terraform init -backend-config=backend.hcl
terraform plan
```

## Check

```bash
# On the VKS cluster: the pushed policy has a UUID name and this label
kubectl get acnp -l ccp-adapter.antrea.tanzu.vmware.com/managedBy=ccp-adapter
kubectl get tiers --sort-by=.spec.priority
```
