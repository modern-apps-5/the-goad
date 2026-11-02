# Pen test: the shop is reachable only through the Avi WAF

This demo shows the music store's security layers stopping an attacker
inside the cluster (decision 49,
[docs/security-architecture.md](../../docs/security-architecture.md)):

- The Antrea default deny in `gitops/music-store-platform` drops traffic
  that goes around Avi: the store pod's IP and its Service.
- The Avi WAF, attached to the shop's route by the L7Rule
  `metal-store-waf` in `gitops/music-store-apps`, answers 403 to SQL and
  PHP injection, and lets a clean request through.

The Grafana board "Pen test" shows five attacks all the time. During the
demo you turn the default deny off, the board shows two attacks getting
through, and you turn it back on.

| File | What it is |
|---|---|
| `flip.sh` | Turns the default deny off and on through Argo CD, and waits until the board shows it. |
| `run.sh` | Starts an attacker pod in the shop's namespace and runs the five checks by hand. |
| `connectivity-check.sh` | The five checks. Runs inside the attacker pod. |
| `attacker.yaml` | The attacker pod, on `alpine/k8s`, and a Role that lets it look up the store pod's IP. |

## The five checks

| # | Check | With the policy and the WAF | Decided by |
|---|---|---|---|
| 1 | The store pod's IP, around Avi | no answer | default deny |
| 2 | The store's Service, around Avi | no answer | default deny |
| 3 | Through Avi, SQL injection | HTTP 403 | WAF |
| 4 | Through Avi, PHP injection | HTTP 403 | WAF |
| 5 | Through Avi, clean request | HTTP 200 | vDefend allows Avi to the store |

## Before the demo

### What you need

- The `vcf` CLI, `kubectl`, `curl` and `jq`.
- A machine on the lab network that resolves `*.goad.gpu.set.lab`.
- A VCF Automation user in the `goad` org who is in the platform
  engineers' group. The group is admin of the project that holds Argo
  CD's namespace, so it may patch the Applications.
- The Grafana `admin` password, from a teammate.

### Make your vcf context

`flip.sh` patches the Argo CD Application `music-store-platform`. Argo
CD's Applications are in the platform engineer's Supervisor Namespace,
named `platform-<suffix>`. You need a vcf context for that namespace,
logged in as yourself.

1. Make a context for the org. The name is yours; `goad` is used below.
   Use an API token that you made in VCF Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

   The vcf CLI makes one more context for each namespace you can use,
   named `<context>:<namespace>:<project>`.

2. Find the one for the Argo CD namespace:

   ```bash
   vcf context list | grep ':platform-'
   ```

   For example `goad:platform-9pq9n:default-project`. Below it is
   `$ARGO_CONTEXT`:

   ```bash
   ARGO_CONTEXT=goad:platform-9pq9n:default-project
   ```

   Pick `platform-<suffix>`, not `platform-tools-<suffix>`.

3. Check it:

   ```bash
   demos/pen-test/flip.sh "$ARGO_CONTEXT" status
   ```

   It prints the Application's state, whether the default deny is
   there, and the five checks. All five must be `1` before the demo
   starts:

   ```
   Argo CD:        Synced, Healthy
   Default deny:   present
   Pen test:       clean=1 phpi=1 pod=1 service=1 sqli=1
   ```

   If the session expires, `vcf context refresh goad`.

### Open the board

Open `http://grafana.goad.gpu.set.lab/d/goad-pen-test` and log in as
`admin`. The board draws the attacker's paths to the store. Violet is
blocked as intended, green is allowed as intended, and red is wrong. The
two paths around Avi end at a wall while the default deny is on.

## Run the demo

1. Show the board with every path as intended: the paths around Avi
   blocked, the attacks through Avi stopped by the WAF, and the clean
   request let through.

2. Turn the default deny off:

   ```bash
   demos/pen-test/flip.sh "$ARGO_CONTEXT" off
   ```

   ```
   Patched Application music-store-platform to drop music-store-default-deny.
   Argo CD pruning the policy. done (6s)
   Pen test checks 1 and 2 failing........ done (41s)
   ```

   Within a minute the board's two paths around Avi turn red and run on
   to the store. The WAF paths do not change: the WAF is a separate
   layer.

3. Turn it back on:

   ```bash
   demos/pen-test/flip.sh "$ARGO_CONTEXT" on
   ```

   Within a minute the paths are blocked again. The board's history keeps
   the gap, which shows when the policy was out.

Each step takes about a minute: a few seconds for Argo CD, then up to two
30-second rounds of the checks. The script prints a dot every 5 seconds
while it waits.

### How the flip works

Argo CD syncs the default deny with self-heal on, so deleting the policy
with `kubectl` would be undone within seconds. Argo CD is not paused.
`off` adds a kustomize patch to the Application `music-store-platform`
that deletes `music-store-default-deny` from what Argo CD renders, and
Argo CD prunes it. `on` removes the patch, and Argo CD creates the policy
again. The Application stays Synced throughout, and nothing else in it
changes.

## After the demo

Run `on` if you did not, and check:

```bash
demos/pen-test/flip.sh "$ARGO_CONTEXT" status
```

The patch is drift from the platform engineer's Terraform, which owns the
Application. A `terraform apply` of `terraform/platform-engineer` while
the default deny is off removes the patch and turns the policy back on.
Its plan shows the patch as a change.

## Run the checks by hand

`run.sh` runs the same five checks from an attacker pod that you start,
and prints the result in the terminal. It needs `kubectl` on the VKS
cluster `music-store`. Get that context from the Supervisor Namespace
of the shop, `music-store-<suffix>`:

```bash
vcf context use goad:music-store-<suffix>:default-project
vcf cluster kubeconfig get music-store
kubectl config use-context <the context it adds>
demos/pen-test/run.sh
```

The shop's name resolves through DNS. If the cluster cannot resolve it,
give the Gateway's address:

```bash
VIP=$(dig +short @172.21.0.90 music.goad.gpu.set.lab A) demos/pen-test/run.sh
```

The drops show in the Antrea policy log on the node that runs the store:

```bash
kubectl exec -n kube-system <antrea-agent-pod> -c antrea-agent -- \
  tail -f /var/log/antrea/networkpolicy/np.log
```

Remove the pod afterwards. It stays until you do:

```bash
demos/pen-test/run.sh --delete
```

## Both layers out, in git

To show every attack getting through, the WAF too, take both layers out
in git and put them back:

1. Commit a change that removes `network-policy.yaml` from
   `gitops/music-store-platform/kustomization.yaml` and
   `metal-store-waf-l7rule.yaml` from
   `gitops/music-store-apps/kustomization.yaml`. Once Argo CD syncs, all
   five checks connect, and the WAF checks answer 200.
2. Revert that commit. Once Argo CD syncs, the checks give the table
   above.

## Troubleshooting

- **`You must be logged in to the server`**: the vcf session expired.
  `vcf context refresh goad`, then run the command again.
- **`Context ... has no namespace`**: the context is the org's, not the
  namespace's. Use the `:platform-<suffix>:` one.
- **`Forbidden` on the patch**: your user is not in the platform
  engineers' group, or the context is for another namespace.
- **`Prometheus not reachable`**: the machine cannot resolve or reach
  `prometheus.goad.gpu.set.lab`. The flip still works; watch the board.
- **Checks 1 and 2 look blocked with the policy off**: they pass when no
  connection opens, so a probe that fails for another reason, such as
  DNS, looks like a drop. Run `run.sh` to see the real answer.
