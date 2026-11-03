# Platform engineer automation: from a change to a running worker

A ten-minute demo of the platform engineer's automation, end to end. Give
the music store's Supervisor Namespace more memory with Terraform, then
grow its VKS cluster from two workers to three with git. Follow each
change: a pull request, the `platform-engineer` workflow on the lab's
runner, Argo CD, and VKS building the new worker.

The point: the platform engineer changes the platform the same way the
developers change code. Terraform for what has to exist first, run from
GitHub with a reviewed plan. Git and Argo CD for everything inside. No
console clicks, no tickets.

This demo changes `main`: it merges two pull requests. `reset.sh` merges a
third to put the lab back.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The starting point | VCF Automation, `music-store-<suffix>` |
| 0:40 | 2. More memory for the namespace | GitHub, `variables.tf`, edit and merge |
| 1:30 | 3. Run the Terraform | GitHub Actions, `platform-engineer` |
| 3:30 | 4. The new limit | VCF Automation, `music-store-<suffix>` |
| 4:00 | 5. A third worker | GitHub, `cluster.yaml`, edit and merge |
| 4:40 | 6. Argo CD picks it up | Argo CD, `music-store` |
| 5:30 | 7. VKS builds the worker | VCF Automation, the cluster `music-store` |
| 9:00 | 8. Back to the console | VCF Automation |

The workflow takes about two minutes and the worker about five. Steps 3
and 7 fill that time.

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- Write access to the GitHub repository `modern-apps-5/the-goad`, to
  merge to `main` and to run workflows.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`.
- For the scripts: `gh`, logged in with that GitHub access, the `vcf`
  CLI, `kubectl`, `jq` and `perl`.

### Make your vcf contexts

The scripts read the music store cluster from its Supervisor Namespace,
`music-store-<suffix>`, and Argo CD's Application from Argo CD's,
`platform-<suffix>`. You need a vcf context for each, logged in as
yourself.

1. Make a context for the org. The name is yours; `goad` is used below.
   Use an API token that you made in VCF Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

   The vcf CLI makes one more context for each namespace you can use,
   named `<context>:<namespace>:<project>`.

2. Find the two:

   ```bash
   vcf context list | grep -e ':music-store-' -e ':platform-'
   ```

   Pick `platform-<suffix>`, not `platform-tools-<suffix>`:

   ```bash
   STORE_CONTEXT=goad:music-store-8q8l6:default-project
   ARGO_CONTEXT=goad:platform-9pq9n:default-project
   ```

   If the session expires, `vcf context refresh goad`.

### Check the lab

```bash
demos/platform-engineer-automation/check.sh "$STORE_CONTEXT" "$ARGO_CONTEXT"
```

It runs the `platform-engineer` workflow as a plan only, and checks the
plan has no changes, `main` is at the start, and the cluster has two ready
workers. It ends with `Ready for the demo.`:

```
terraform: No changes. Your infrastructure matches the configuration.

On main:      namespace music-store memory_limit 48Gi; cluster workers replicas 2
Argo CD:      music-store Synced, Healthy, at 9e05863
Cluster:      workers desired 2, ready 2
  music-store-k4sgg-pwtc2  Running
  music-store-workers-6xtl4-wnr4j-8n8n5  Running
  music-store-workers-6xtl4-wnr4j-gjwhn  Running

Ready for the demo.
```

A plan with changes means someone changed the lab or `main` by hand. Find
out whose before the demo; the demo's apply would apply them too.

### Browser tabs

1. VCF Automation, `https://auto.gpu.set.lab`, org `goad`, Build &
   Deploy, the default project, namespace `music-store-<suffix>`.
2. GitHub: `terraform/platform-engineer/variables.tf`.
3. GitHub: Actions, `platform-engineer`.
4. GitHub: `gitops/music-store/cluster.yaml`.
5. Argo CD, Application `music-store`. Open it from namespace
   `platform-<suffix>`, the GitOps tab, and log in with "VCF Automation".

### Terminal

Leave this running where you can see it. It prints the state every 15
seconds:

```bash
demos/platform-engineer-automation/status.sh "$STORE_CONTEXT" "$ARGO_CONTEXT" watch
```

## Run the demo

### 1. The starting point (0:00)

Tab 1, namespace `music-store-<suffix>`.

**Show**

- The namespace's limits: memory 48 GiB.
- VKS cluster `music-store`: one control plane, two workers.

**Why**: the shop needs more capacity. The namespace limit is the
platform engineer's to set, inside the quota the cloud admin gave the org.

### 2. More memory for the namespace (0:40)

Tab 2, `variables.tf`. Edit in the browser.

**Show**

- In `music-store = {`, change `memory_limit = "48Gi"` to `"64Gi"`.
- Commit to a new branch, open the pull request, merge it.

**Why**: the namespace is Terraform. The change is a reviewed pull
request, not a console click.

### 3. Run the Terraform (1:30)

Tab 3, Actions, `platform-engineer`. Run workflow, tick "Apply after the
plan", run it on `main`.

**Show**

- The job runs on a `self-hosted, lab` runner.
- The run's summary: the plan, one change, an update in place of
  `vcfa_supervisor_namespace.namespaces["music-store"]`, `memory_limit`
  from `48Gi` to `64Gi`.
- The step Apply, green.

**Why**: GitHub's own runners cannot reach the lab, so the job runs on a
runner inside it, a container on the Supervisor. Terraform keeps its
state in the lab's Gitea, locked, the same for a run from GitHub and one
from a laptop. The secrets are GitHub secrets, never in git. A person
starts the run, and it applies only on `main` and only when ticked.

### 4. The new limit (3:30)

Tab 1, reload.

**Show**: the namespace's memory limit, 64 GiB.

**Why**: what the workflow applied is what VCF Automation shows. No one
logged in to change it.

### 5. A third worker (4:00)

Tab 4, `cluster.yaml`. Edit in the browser.

**Show**

- Under `machineDeployments`, `name: workers`, change `replicas: 2` to
  `replicas: 3`.
- Commit to a new branch, open the pull request, merge it.
- No workflow to start.

**Why**: what is inside the namespaces is not Terraform. It is YAML in
git, and Argo CD applies it. Terraform only handed this folder to Argo CD.

### 6. Argo CD picks it up (4:40)

Tab 5, Application `music-store`. Click Refresh if it has not synced yet.

**Show**

- The new commit at the top, Synced.
- The `Cluster` `music-store`, its live manifest: workers `replicas: 3`.
- The terminal: `Argo CD: ... at <the merge commit>`, then
  `workers desired 3, ready 2`, and a third `Machine` in `Provisioning`.

**Why**: Argo CD reads git every few minutes and applies what changed.
It is a VCF service, not a tool the platform engineer installed and
patches.

### 7. VKS builds the worker (5:30)

Tab 1, the cluster `music-store`.

**Show**

- The node pool `workers`: three, one being created.
- The new virtual machine coming up in the namespace.
- The terminal, until `workers desired 3, ready 3`.

**Why**: VKS turns one number in git into a VM, joined to the cluster and
ready for pods. Its lifecycle is VCF's, not the platform engineer's.

### 8. Back to the console (9:00)

Tab 1, namespace `music-store-<suffix>`.

**Show**: memory 64 GiB, three workers Ready.

**Why**: two pull requests, one approved workflow run, and nothing done
by hand. Every change is in git's history, with a person behind it.

## After the demo

```bash
demos/platform-engineer-automation/reset.sh "$STORE_CONTEXT"
```

It opens and merges one pull request with `48Gi` and `replicas: 2`,
waits for Argo CD and VKS to remove the third worker, then runs the
`platform-engineer` workflow with apply. It takes about ten minutes. It
can run again after a failure: it skips what is already back. Then
check:

```bash
demos/platform-engineer-automation/check.sh "$STORE_CONTEXT" "$ARGO_CONTEXT"
```

## Troubleshooting

- **The plan in step 3 has more than one change**: someone changed the
  lab or `main` since `check.sh`, and the run applied their change too.
  Find out whose it is. Run `check.sh` close to the demo.
- **The run waits on `Acquiring state lock`**: another run of this root is
  going. It waits up to five minutes. Actions shows the other run.
- **The run is Queued and does not start**: no lab runner is free. See
  `terraform/runner`.
- **Argo CD does not sync after the merge**: click Refresh on
  `music-store`. If it stays OutOfSync, click Sync.
- **The third `Machine` stays in `Provisioning`**: open it in tab 5; its
  conditions say what VKS waits on. A namespace out of memory or storage
  shows there.
- **`You must be logged in to the server`**: the vcf session expired.
  `vcf context refresh goad`, then run the script again.
- **`reset.sh` gives up waiting for two workers**: the Machine being
  deleted is waiting for its node to drain. Run `reset.sh` again.
