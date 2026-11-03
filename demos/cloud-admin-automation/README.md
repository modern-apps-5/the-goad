# Cloud admin automation: from a change to the org's quota

A seven-minute demo of the cloud admin's automation, end to end. The
platform engineer needs more reserved memory for Private AI Services.
Raise the org `goad`'s memory reservation in its region quota, and follow
the change: a pull request, the `cloud-admin` workflow on the lab's
runner, its Terraform roots, and the new quota in VCF Automation.

The point: the cloud admin runs the org like code. Every change to the
org is a reviewed pull request and an approved plan, run by the same
automation as every other persona. Nothing is set by hand in the provider
console.

This demo changes `main`: it merges one pull request. `reset.sh` merges a
second to put the lab back.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The org's quota | VCF Automation provider portal, org `goad` |
| 0:40 | 2. Why it changes | VCF Automation, org `goad`, `private-ai-<suffix>` |
| 1:10 | 3. Raise the reservation | GitHub, `lab.auto.tfvars`, edit and merge |
| 2:00 | 4. Run the Terraform | GitHub Actions, `cloud-admin` |
| 5:00 | 5. The new quota | VCF Automation provider portal, org `goad` |
| 5:40 | 6. What the run did not change | GitHub Actions, the run's summary |

The workflow takes about three minutes. Step 4 fills that time.

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- Write access to the GitHub repository `modern-apps-5/the-goad`, to
  merge to `main` and to run workflows.
- A VCF Automation provider login, in the System org, to show the org's
  quota.
- A VCF Automation user in org `goad`, to show the namespace in step 2.
- For the scripts: `gh`, logged in with that GitHub access, `jq` and
  `perl`.

### Check the lab

```bash
demos/cloud-admin-automation/check.sh
```

It checks `main` is at the start, then runs the `cloud-admin` workflow as
a plan only and checks every job plans no change. It ends with
`Ready for the demo.`:

```
On main: zone west-1 memory_reservation_mib 32768

Planning the cloud admin's roots, without apply.
Run: https://github.com/modern-apps-5/the-goad/actions/runs/...
agentminder: No changes. Your infrastructure matches the configuration.
ops: No changes. Your infrastructure matches the configuration.
org: No changes. Your infrastructure matches the configuration.
org-config: No changes. Your infrastructure matches the configuration.

Ready for the demo.
```

A plan with changes means someone changed the lab or `main` by hand. Find
out whose before the demo; the demo's apply would apply them too.

### Browser tabs

1. VCF Automation provider portal, `https://auto.gpu.set.lab/provider`,
   Organizations, `goad`, its region quota.
2. VCF Automation, org `goad`, Build & Deploy, the default project,
   namespace `private-ai-<suffix>`.
3. GitHub: `terraform/cloud-admin/org/lab.auto.tfvars`.
4. GitHub: Actions, `cloud-admin`.

## Run the demo

### 1. The org's quota (0:00)

Tab 1, org `goad`, region quota.

**Show**

- Region `ans-cluster`, zone `west-1`: CPU and memory limits, CPU and
  memory reservations. Memory reservation 32 GiB.
- The VM classes and the storage policy the org may use.

**Why**: the quota is the ceiling for every namespace the platform
engineer makes. The cloud admin sets it once, and the platform engineer
self-serves inside it.

### 2. Why it changes (0:40)

Tab 2, namespace `private-ai-<suffix>`.

**Show**: the namespace's memory reservation.

**Why**: Private AI Services runs as vSphere Pods, and a vSphere Pod's
memory request is a reservation. More models need more reserved memory
than the org allows. The platform engineer asked for it.

### 3. Raise the reservation (1:10)

Tab 3, `lab.auto.tfvars`. Edit in the browser.

**Show**

- In `zone_allocations`, `"west-1"`, change
  `memory_reservation_mib = 32768` to `49152`.
- Commit to a new branch, open the pull request, merge it.

**Why**: the org's settings are in git, not secret, and the same for
everyone. The change is reviewed like code.

### 4. Run the Terraform (2:00)

Tab 4, Actions, `cloud-admin`. Run workflow, tick "Apply after the plan",
run it on `main`.

**Show**

- Four jobs: `org`, then `org-config`, then `agentminder`, each waiting
  for the one before, and `ops` beside them.
- Each job runs on a `self-hosted, lab` runner.
- The job `org`, its plan: one update in place of
  `vcfa_org_region_quota.this`, `memory_reservation_mib` from `32768` to
  `49152`. Then the step Apply, green.

**Why**: one Terraform root per stage: the org, what is inside it, and
AgentMinder, plus the VCF Operations dashboards and alerts in `ops`. One
run keeps them in order. The runner is inside
the lab, the state is in the lab's Gitea, locked, and the provider
password is a GitHub secret. A person starts the run, and it applies only
on `main` and only when ticked.

### 5. The new quota (5:00)

Tab 1, reload.

**Show**: zone `west-1`, memory reservation 48 GiB.

**Why**: what the workflow applied is what VCF Automation shows. No one
logged in to the provider console to change it.

### 6. What the run did not change (5:40)

Tab 4, the run's summary.

**Show**: `org-config`, `agentminder` and `ops`, "No changes."

**Why**: Terraform changes only what git changed. The org's users,
roles, load balancer, AgentMinder and VCF Operations content are as they
were. The platform
engineer can now give `private-ai` more reservation, with their own
workflow.

## After the demo

```bash
demos/cloud-admin-automation/reset.sh
```

It opens and merges a pull request with `memory_reservation_mib = 32768`,
then runs the `cloud-admin` workflow with apply. It takes about four
minutes. Then check:

```bash
demos/cloud-admin-automation/check.sh
```

## Troubleshooting

- **The plan in step 4 has more than one change**: someone changed the
  lab or `main` since `check.sh`, and the run applied their change too.
  Find out whose it is. Run `check.sh` close to the demo.
- **The job `org` fails on the quota**: the region does not have that
  much memory to reserve. Use a smaller number.
- **The run waits on `Acquiring state lock`**: another run of the same
  root is going. It waits up to five minutes. Actions shows the other run.
- **The run is Queued and does not start**: no lab runner is free. See
  `terraform/runner`.
- **The provider portal shows the old value**: reload without the cache,
  or open the org again from Organizations.
