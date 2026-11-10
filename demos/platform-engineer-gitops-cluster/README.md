# Platform engineer: a VKS cluster with add-ons, managed by Argo CD

One command builds a new VKS cluster from git, with Headlamp, Prometheus
and Telegraf. One pull request adds the namespace and the manifests, the
`platform-engineer` workflow makes the namespace and the Argo CD
Application, and Argo CD does the rest.

| Add-on | What it adds | How the cluster gets it |
|---|---|---|
| Headlamp | A Kubernetes UI in the browser | An `AddonInstall`, `gitops/headlamp.yaml` |
| cert-manager | Certificates. Headlamp does not work without it | An `AddonInstall`, `gitops/cert-manager.yaml` |
| Prometheus | Metrics and alerting | The label `addons.kubernetes.vmware.com/platform-observability: enabled` |
| Telegraf | An agent that collects metrics | The same label |

The platform-observability Supervisor Service installs Prometheus and
Telegraf on every cluster with its label, and onboards the cluster to VCF
Operations. The music store and platform tools clusters have the same
label.

The point: a new cluster and everything on it is a reviewed change in git.
Argo CD keeps it that way, and the add-ons come from VCF, so nobody finds,
mirrors or patches a chart.

This demo changes `main`. `deploy.sh` merges one pull request, and
`reset.sh` merges two more to put the lab back.

> **Not yet run in the lab.** The cluster comes from
> `gitops/platform-tools/cluster.yaml`, and the `AddonInstall` objects from
> `gitops/platform-tools/cert-manager.yaml`. Headlamp's release name, the
> names of the Prometheus and Telegraf pods, and the times below are not
> checked yet. Do a full run first.

## Steps

| Step | Screen |
|---|---|
| 1. What goes into git | Terminal or GitHub |
| 2. Deploy | Terminal, GitHub Actions |
| 3. Argo CD builds the cluster | Argo CD, VCF Automation |
| 4. The add-ons | Terminal |
| 5. See the cluster in Headlamp | Headlamp |

The workflow takes about two minutes and the cluster about fifteen. To
keep the demo short, run `deploy.sh` before the audience arrives and show
the finished Application.

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- Write access to the GitHub repository `modern-apps-5/the-goad`, to merge
  to `main` and to run workflows.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`.
- `gh`, logged in with that GitHub access, the `vcf` CLI, `kubectl`, `jq`
  and `perl`.
- Room in the org's region quota for one more namespace: 40 GHz, 48 GiB
  and 150 GiB of storage.

### Make your vcf context

Make a context for the org. The name is yours; `goad` is used below. Use
an API token that you made in VCF Automation:

```bash
vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
  --tenant-name goad --api-token <your API token>
```

Find Argo CD's namespace. Pick `platform-<suffix>`, not
`platform-tools-<suffix>`:

```bash
vcf context list | grep ':platform-'

ARGO_CONTEXT=goad:platform-<suffix>:default-project
```

If the session expires, `vcf context refresh goad`.

### Check Headlamp's release

`gitops/headlamp.yaml` in this folder pins
`headlamp.kubernetes.vmware.com.0.45.0-vmware.2-vks.1`, Headlamp
0.45.0+vmware.2-vks.1 from VKS Add-ons v3.8.0+20261021. The release notes
give only the version, so check that the lab has a release by that name,
in any Supervisor Namespace context:

```bash
vcf context use "$ARGO_CONTEXT"
vcf addon available list headlamp
```

If the name differs, change the file through a pull request.

### Check the lab

```bash
demos/platform-engineer-gitops-cluster/check.sh "$ARGO_CONTEXT"
```

It ends with `Ready for the demo.`. A plan with changes means someone
changed the lab or `main` by hand. Find out whose before the demo;
`deploy.sh` would apply them too.

### Browser tabs

1. GitHub: Actions, `platform-engineer`.
2. Argo CD. Open it from namespace `platform-<suffix>`, the GitOps tab, and
   log in with "VCF Automation".
3. VCF Automation, `https://auto.gpu.set.lab`, org `goad`, Build & Deploy,
   the default project.

## Run the demo

### 1. What goes into git

Open `gitops/` in this folder: `cluster.yaml` and `headlamp.yaml`.

**Show**

- The labels on the `Cluster`. `platform-observability` brings Prometheus
  and Telegraf, with nothing else in git.
- The `AddonInstall`: the add-on, its pinned release, and the label that
  selects the cluster.

**Why**: the cluster is one short manifest. An add-on is a label, and
at most one more manifest.

### 2. Deploy

```bash
demos/platform-engineer-gitops-cluster/deploy.sh "$ARGO_CONTEXT"
```

It prints the pull request, the workflow run, and then dots until Argo CD
reports the cluster ready. The plan adds three things: the namespace, its
`ManagedEntity`, and its `Application`.

**Show**: the pull request, then the run in tab 1.

**Why**: Terraform makes only what has to exist first. No one is logged in
to the namespace.

### 3. Argo CD builds the cluster

Tab 2, Application `vks-addons`. Tab 3, namespace `vks-addons-<suffix>`.

**Show**

- The `Cluster` and the two `AddonInstall` objects, Synced.
- The cluster coming up in VCF Automation.

**Why**: Argo CD reports the `Cluster` Healthy only when it is ready.
Delete an `AddonInstall` by hand, and Argo CD puts it back.

### 4. The add-ons

Argo CD reports an `AddonInstall` as soon as it exists, so look at the
add-ons themselves. Make the contexts for the new namespace and for the
cluster:

```bash
vcf context refresh goad
vcf context list | grep ':vks-addons-'

CLUSTER_CONTEXT=goad:vks-addons-<suffix>:default-project

demos/platform-engineer-gitops-cluster/status.sh "$ARGO_CONTEXT" "$CLUSTER_CONTEXT"
vcf context use "$CLUSTER_CONTEXT"
vcf addon install list --cluster-name vks-addons

vcf cluster kubeconfig get vks-addons
kubectl config get-contexts

WORKLOAD_CONTEXT=<the context for the cluster vks-addons>

kubectl --context "$WORKLOAD_CONTEXT" get pods -A | grep -iE 'headlamp|cert-manager|prometheus|telegraf'
```

Wait until `cert-manager` and `headlamp` show `READY` `True`. They install
at the same time, and Headlamp may show `False` until cert-manager is
ready. Prometheus and Telegraf come up in the cluster once
platform-observability has onboarded it.

**Show**: the add-ons `True`, and the pods of all four.

**Why**: two `AddonInstall` objects and one label, and the cluster has a
UI, metrics and a metrics agent.

### 5. See the cluster in Headlamp

This step reads the cluster. It is the one step done by hand, and the
login goes away with the cluster.

```bash
kubectl --context "$WORKLOAD_CONTEXT" -n headlamp get svc
kubectl --context "$WORKLOAD_CONTEXT" create clusterrolebinding headlamp-view \
  --serviceaccount=headlamp:headlamp --clusterrole=view
```

Copy a token without printing it, on macOS:

```bash
kubectl --context "$WORKLOAD_CONTEXT" -n headlamp create token headlamp | pbcopy
```

Elsewhere, run it without `pbcopy` in a terminal the audience cannot see.
Open the Service's external IP. If it has none, use
`kubectl --context "$WORKLOAD_CONTEXT" -n headlamp port-forward svc/headlamp 8080:80`
and open `http://localhost:8080`. Paste the token.

**Show**: the three nodes, and the workloads the add-ons made.

**Why**: from a pull request to a cluster teams can use.

## After the demo

```bash
demos/platform-engineer-gitops-cluster/reset.sh "$ARGO_CONTEXT" "$CLUSTER_CONTEXT"
```

It merges a pull request that removes the cluster and the add-ons, waits
for Argo CD to prune them, merges a second that removes the namespace, and
runs the `platform-engineer` workflow with apply. It can run again after a
failure. Then check:

```bash
demos/platform-engineer-gitops-cluster/check.sh "$ARGO_CONTEXT"
```

## Troubleshooting

- **The plan in `deploy.sh` has more than three additions**: someone
  changed the lab or `main` since `check.sh`, and the run applied their
  change too. Find out whose it is.
- **`gh pr merge` refuses the merge**: `main` needs an approval, and only
  a maintainer or admin can bypass it. See `CONTRIBUTING.md`.
- **The run is Queued and does not start**: no lab runner is free. See
  `terraform/runner`.
- **Argo CD does not sync after the workflow**: click Refresh on
  `vks-addons`. If it stays OutOfSync, click Sync.
- **An add-on stays `READY` `False`**: its `ClusterAddon` says what it
  waits on: `kubectl --context "$CLUSTER_CONTEXT" get clusteraddons`.
- **`AddonInstall` is Synced but the add-on is missing**: a wrong release
  name or a label that does not match. Compare the file with
  `vcf addon available list <add-on>`.
- **No Prometheus or Telegraf pods**: check that the `Cluster` has the
  label `addons.kubernetes.vmware.com/platform-observability: enabled`,
  and that the platform-observability Supervisor Service is running on the
  Supervisor. Its addon also needs helm-controller in the cluster.
- **`vks-addons` stays in `Provisioning`**: the namespace may be out of
  memory or storage: `kubectl --context "$CLUSTER_CONTEXT" get machines`,
  then `describe` the one that is stuck.
- **`You must be logged in to the server`**: the vcf session expired.
  `vcf context refresh goad`, then run the script again.
