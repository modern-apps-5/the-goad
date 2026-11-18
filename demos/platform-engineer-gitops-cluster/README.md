# Platform engineer: a VKS cluster with add-ons, managed by Argo CD

Argo CD builds a new VKS cluster and its add-ons from git, and then the
cluster is registered as an Argo CD target with the `ManagedEntity` CRD.
**No Terraform.** The scripts `kubectl apply` an Argo CD `Application` and
two `ManagedEntity` objects straight into Argo CD's namespace; Argo CD does
the rest from git.

| Add-on | What it adds | How the cluster gets it |
|---|---|---|
| Headlamp | A Kubernetes UI in the browser | An `AddonInstall`, `gitops/headlamp.yaml` |
| cert-manager | Certificates. Headlamp does not work without it | An `AddonInstall`, `gitops/cert-manager.yaml` |
| Istio | A service mesh: mTLS, traffic policy and telemetry between workloads | An `AddonInstall`, `gitops/istio.yaml` |
| Prometheus | Metrics and alerting | The label `addons.kubernetes.vmware.com/platform-observability: enabled` |
| Telegraf | An agent that collects metrics | The same label |

The platform-observability Supervisor Service installs Prometheus and
Telegraf on every cluster with its label, and onboards the cluster to VCF
Operations. The add-ons do **not** travel through the cluster target: the
Supervisor installs them from the `AddonInstall`s and the label. The target
is what lets Argo CD deploy *workloads* into the cluster afterwards.

The point: a new cluster and everything on it is git, and Argo CD keeps it
that way. Nothing is created by hand in the namespace or the cluster, and
the add-ons come from VCF, so nobody finds, mirrors or patches a chart.
The exceptions are the logins in steps 4 and 6: the cluster's VCF
Automation authenticator and Headlamp's service account. They go away with
the cluster.

> **Not yet run in the lab.** Headlamp's release name, the add-on pod names
> and the times below are copied from the platform tools cluster and not
> checked yet. Do a full run first.

## How it works

Three objects, applied into Argo CD's namespace (`platform-<suffix>`), and
one git directory Argo CD syncs:

```
                 kubectl apply (deploy.sh, no Terraform)
                              │
   ┌──────────────────────────┼───────────────────────────┐
   ▼                          ▼                            ▼
ManagedEntity            Application A              ManagedEntity
"vks-addons-ns"          "vks-addons"              "vks-addons-cluster"
registers the            syncs gitops/ into        registers the cluster
namespace as a   ──────▶ the namespace:    ──────▶ as an Argo CD target
destination              Cluster + add-ons         (applied once Healthy)
                              │
                              ▼  Supervisor installs
                     Headlamp, cert-manager, Istio,
                     Prometheus, Telegraf
```

- **`argocd/managedentity-namespace.yaml`** registers the reused Supervisor
  Namespace as an Argo CD destination (`vks-addons-ns`), so Application A
  can deploy into it.
- **`argocd/application.yaml`** (Application A, `vks-addons`) syncs
  `gitops/` — the `Cluster` and the three `AddonInstall`s — into that
  namespace. Argo CD reports it Healthy only when the cluster is ready.
- **`argocd/managedentity-cluster.yaml`** registers the VKS cluster itself
  as an Argo CD target (`vks-addons-cluster`). This is the point of the
  demo.
- **`test/`** (Application B) is a test only: it deploys a tiny workload
  into the cluster through that target, to prove it works. `deploy.sh` does
  not run it.

| File | What it is |
|---|---|
| `deploy.sh` | Applies the namespace target, Application A, waits, then the cluster target. |
| `reset.sh` | Deletes it all again. The reused namespace is left as it was. |
| `status.sh` | The Applications, the targets, the cluster and its add-ons. |
| `check.sh` | Pre-demo check: contexts resolve, releases set, nothing already deployed. |
| `test-app.sh` | The test: deploy a workload into the cluster through the target. |
| `common.sh` | Shared values and helpers. Not run on its own. |
| `gitops/` | What Argo CD syncs: `cluster.yaml`, `headlamp.yaml`, `cert-manager.yaml`, `istio.yaml`. |
| `argocd/` | The `Application` and `ManagedEntity` objects `deploy.sh` applies. |
| `test/` | Application B and its workload, for `test-app.sh`. |

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`.
- `gh` is **not** needed. You need the `vcf` CLI, `kubectl` and `jq`.
- **An existing Supervisor Namespace to reuse**, with room for one VKS
  cluster. The demo does not create a namespace. Argo CD must be allowed to
  deploy into it; `deploy.sh` registers it as a destination with a
  `ManagedEntity`.
- The manifests must be on the git revision Argo CD reads. The default is
  `main`, so merge this folder to `main` first, or pass your branch as the
  third argument once it is pushed.

### Make your vcf contexts

Make a context for the org. The name is yours; `goad` is used below:

```bash
vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
  --tenant-name goad --api-token <your API token>
```

Find Argo CD's vSphere namespace (`platform-<suffix>`, not `platform-tools-<suffix>`)(This is any vSphere namespace where you have deployed an ArgoCD Instance)
and the vSphere namespace you will reuse for the cluster:

```bash
vcf context list | grep ':platform-'
ARGO_CONTEXT=goad:platform-<suffix>:default-project

vcf context list | grep ':<your namespace>-'
NS_CONTEXT=goad:<your namespace>:default-project
```

If a session expires, `vcf context refresh goad`.

### Check the lab

```bash
demos/platform-engineer-gitops-cluster/check.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
```

It ends with `Ready for the demo.`.

## Run the demo

### 1. What goes into git

Open `gitops/` and `argocd/`.

**Show**

- `gitops/cluster.yaml`: the labels on the `Cluster`. `platform-observability`
  brings Prometheus and Telegraf, with nothing else in git.
- `gitops/headlamp.yaml`: the `AddonInstall` — the add-on, its pinned
  release, and the label that selects the cluster.
- `argocd/managedentity-cluster.yaml`: the one object that registers the
  cluster as an Argo CD target.

**Why**: the cluster is one short manifest, an add-on is a label and at most
one more, and the target is one `ManagedEntity`.

### 2. Deploy

```bash
demos/platform-engineer-gitops-cluster/deploy.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
```

It registers the namespace, creates Application A, waits for the cluster
(about fifteen minutes), and then registers the cluster as a target.

**Show**: in Argo CD, the Application `vks-addons` syncing; in VCF
Automation, the cluster coming up.

### 3. The cluster is an Argo CD target

In Argo CD, Settings, Clusters: `vks-addons-ns` and `vks-addons-cluster`.

**Show**: the cluster listed as a destination Argo CD can deploy into.

**Why**: from a pull request to a cluster teams can deploy to, all through
Argo CD, with no Terraform.

### 4. Connect to the cluster

A cluster that Argo CD makes does not yet accept VCF Automation logins:
`kubectl` against it fails with `could not complete Concierge credential
exchange: login failed: authentication failed`. Register the VCF
Automation JWT authenticator on the cluster once, then export its
kubeconfig and make a vcf context for it:

```bash
vcf context use "$NS_CONTEXT"
vcf cluster register-vcfa-jwt-authenticator pe-gitops-cluster

vcf cluster kubeconfig get pe-gitops-cluster --export-file ~/pe-gitops-cluster.kubeconfig
kubectl --kubeconfig ~/pe-gitops-cluster.kubeconfig config get-contexts -o name
```

The context in the file is named
`vcf-cli-pe-gitops-cluster-<namespace>@pe-gitops-cluster-<namespace>`, with
the namespace of `NS_CONTEXT`. `--type k8s` is required:

```bash
vcf context create pe-gitops-cluster --type k8s \
  --kubeconfig ~/pe-gitops-cluster.kubeconfig \
  --kubecontext vcf-cli-pe-gitops-cluster-<namespace>@pe-gitops-cluster-<namespace>

vcf context use pe-gitops-cluster
```

`vcf context use` does not switch plain `kubectl`: the vcf context keeps
the cluster in its own file, and `kubectl` reads only `~/.kube/config`.
Point `kubectl` at the file, with `~/.kube/config` after it so the
namespace contexts still resolve for the scripts:

```bash
export KUBECONFIG=~/pe-gitops-cluster.kubeconfig:~/.kube/config
kubectl config current-context
kubectl get nodes
```

The file comes first, so its current context, the cluster, is the one
`kubectl` uses, and its entries win over any left in `~/.kube/config`
from an earlier cluster of the same name. Back to the namespace:
`unset KUBECONFIG`.

The first `kubectl` asks for your VCF Automation API token. There are three
nodes, all `Ready`. If `kubectl` is `Forbidden` right after the cluster
comes up, wait a minute: VKS gives your namespace role its rights in the
cluster a few minutes after the nodes are up.

### 5. The add-ons

```bash
demos/platform-engineer-gitops-cluster/status.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
kubectl get pods -A | grep -iE 'headlamp|cert-manager|istio|prometheus|telegraf'
```

**Show**: the `AddonInstall`s, and the five add-ons' pods in the cluster.
Istio's are in `istio-system`: `istiod`, an `istio-cni-node` on every
node, and `istio-support`.

### 6. Log in to Headlamp

Headlamp asks for a Kubernetes token. Make a service account for the login,
give it read access to the cluster, and copy a token for it. With
`KUBECONFIG` from step 4:

```bash
kubectl -n headlamp create serviceaccount headlamp-login
kubectl create clusterrolebinding headlamp-login \
  --serviceaccount=headlamp:headlamp-login --clusterrole=view

kubectl -n headlamp create token headlamp-login --duration=8h | pbcopy
```

`pbcopy` copies the token on macOS without printing it. Elsewhere, run the
last command without it in a terminal the audience cannot see. A token
lasts until `--duration` runs out; make a new one with the same command.
`--clusterrole=cluster-admin` instead of `view` lets you change things from
Headlamp.

Find Headlamp's address:

```bash
kubectl -n headlamp get svc
```

Open the Service's `EXTERNAL-IP`. If it has none, run
`kubectl -n headlamp port-forward svc/<the Service> 8080:80` and open
`http://localhost:8080`. Paste the token.

**Show**: the three nodes, and the workloads the add-ons made.

### 7. Istio

The mesh is on, but nothing is in it yet: Istio adds its sidecar only to
pods in a namespace with the label `istio-injection=enabled`. The test
workload's namespace is a good one to show it with (see "Test the target"
below):

```bash
kubectl label namespace demo istio-injection=enabled
kubectl -n demo rollout restart deployment
kubectl -n demo get pods
```

**Show**: the pods now have two containers, the workload and
`istio-proxy`.

**Why**: a mesh for every cluster is one label in git, with no chart.

The Istio add-on has no Kiali and no ingress gateway. For a Kiali
dashboard, install Istio's sample Prometheus and Kiali by hand; they are
not production setups (no persistence, anonymous login) and pull their
images from `quay.io` and `docker.io`:

```bash
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.28/samples/addons/prometheus.yaml
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.28/samples/addons/kiali.yaml
kubectl -n istio-system port-forward svc/kiali 20001:20001
```

and open `http://localhost:20001`. They go away with the cluster.

## Test the target (optional, not part of the demo)

Prove Argo CD can deploy into the cluster through the target:

```bash
demos/platform-engineer-gitops-cluster/test-app.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
# remove it again
demos/platform-engineer-gitops-cluster/test-app.sh --delete "$ARGO_CONTEXT"
```

It deploys a tiny unprivileged nginx into namespace `demo` of the cluster
and waits for Argo CD to report it Healthy.

## After the demo

```bash
demos/platform-engineer-gitops-cluster/reset.sh "$ARGO_CONTEXT" "$NS_CONTEXT"
```

It removes the test workload, deletes Application A (Argo CD prunes the
cluster and the add-ons), waits for the cluster to be gone, and removes the
two targets. The reused namespace is left as it was.

The Headlamp service account and binding go with the cluster. Remove the
cluster's vcf context and kubeconfig yourself, and any entries for the
cluster in `~/.kube/config`. They are stale once the cluster is gone, and
the next cluster of the same name has a new CA, so `kubectl` with them
fails on the certificate:

```bash
unset KUBECONFIG
vcf context delete pe-gitops-cluster
rm ~/pe-gitops-cluster.kubeconfig

kubectl config get-contexts -o name | grep pe-gitops-cluster
kubectl config delete-context vcf-cli-pe-gitops-cluster-<namespace>@pe-gitops-cluster-<namespace>
kubectl config delete-cluster pe-gitops-cluster-<namespace>
```

The last two say `not found` if there was nothing to remove.

## Testing from a branch

Argo CD reads the manifests from a git revision, so they must be pushed.
While testing this branch, pass it as the third argument:

```bash
demos/platform-engineer-gitops-cluster/deploy.sh "$ARGO_CONTEXT" "$NS_CONTEXT" <your-branch>
demos/platform-engineer-gitops-cluster/test-app.sh "$ARGO_CONTEXT" "$NS_CONTEXT" <your-branch>
```

## Troubleshooting

- **Application A stays `OutOfSync` or `Missing`**: the revision has no
  manifests at `gitops/`. Merge this folder to `main`, or pass your pushed
  branch as the third argument. Click Refresh, then Sync, in Argo CD.
- **Application A `Unknown` with "cluster … not found"**: the namespace
  destination is not ready. Check `kubectl -n <argo ns> get managedentity
  vks-addons-ns` and that the Argo CD cluster secret appeared.
- **`AddonInstall` is Synced but the add-on is missing**: a wrong release
  name or a label that does not match. Compare the file with
  `vcf addon available list <add-on>`.
- **No Prometheus or Telegraf pods**: check the `Cluster` has the label
  `addons.kubernetes.vmware.com/platform-observability: enabled`, and that
  the platform-observability Supervisor Service is running.
- **The cluster stays in `Provisioning`**: the namespace may be out of
  memory or storage. `kubectl --context "$NS_CONTEXT" get machines`, then
  `describe` the one that is stuck.
- **`could not complete Concierge credential exchange: login failed:
  authentication failed`**: the cluster has no VCF Automation
  authenticator. Run `vcf cluster register-vcfa-jwt-authenticator
  pe-gitops-cluster` from `NS_CONTEXT` (step 4).
- **`Context type is invalid: context pe-gitops-cluster creation failed`**:
  `vcf context create` needs `--type k8s`. Delete the half-made context
  with `vcf context delete pe-gitops-cluster` first if it exists.
- **`kubectl config current-context` is still the namespace after `vcf
  context use pe-gitops-cluster`**: `kubectl` does not read the vcf
  context's file. Set `KUBECONFIG` as in step 4.
- **`nodes is forbidden: User "<you>" cannot list resource "nodes"`**: you
  are logged in, but VKS has not yet given your namespace role its rights
  in the new cluster. Wait a minute and run it again.
- **`x509: certificate signed by unknown authority`** against the cluster:
  `kubectl` is using an entry in `~/.kube/config` left from an earlier
  `pe-gitops-cluster`. Set `KUBECONFIG` as in step 4, and remove the old
  entries (see "After the demo").
- **`x509: certificate signed by unknown authority`** on `vcf context
  create goad`: the CLI does not trust the lab's CA. Pass it with
  `--ca-certificate <the vc01.gpu.set.lab CA file>`, or use
  `--insecure-skip-tls-verify`.
- **Headlamp rejects the token**: the token expired, or it came from a
  Secret that is not a service account token, such as an image pull
  secret. Make a new one with `kubectl -n headlamp create token
  headlamp-login`.
- **Istio was also added from the VCF Automation UI**: the UI makes its
  own install for the cluster, a second one beside `gitops/istio.yaml`.
  Remove the UI's, and leave the cluster's Istio to git.
- **Pods have no `istio-proxy`**: the namespace has no
  `istio-injection=enabled` label, or the pods started before it was set.
  Label it and `rollout restart`.
- **`You must be logged in to the server`**: the vcf session expired.
  `vcf context refresh goad`, then run the script again.
