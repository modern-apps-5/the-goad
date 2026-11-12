# Pen test on the dashboard: turn the security layers off and on

One of two pen test demos. This one is watched on the Grafana board "Pen
test": you take the music store's security layers out one at a time, the
attacks each one stopped get through on the board, and you put them back. The other,
[pen-test-manual](../pen-test-manual), starts an attacker pod by hand and
prints the same checks in a terminal.

What the checks show (decision 49,
[docs/security-architecture.md](../../docs/security-architecture.md)):

- The Antrea default deny in `gitops/music-store-platform` drops traffic
  that goes around Avi: the store pod's IP and its Service.
- The Avi WAF, attached to the shop's route by the L7Rule
  `metal-store-waf` in `gitops/music-store-apps`, answers 403 to SQL and
  PHP injection, and lets a clean request through.

| File | What it is |
|---|---|
| `flip.sh` | Turns the default deny, the WAF, or both off and on through Argo CD, and waits until the board shows it. |

The checks run all the time, from a blackbox exporter in namespace
`pen-test` (`gitops/music-store-platform/pen-test.yaml`), every 30
seconds. Nothing has to be started for the board.

## The checks

| # | Check | With the policy and the WAF | Decided by |
|---|---|---|---|
| 1 | The store pod's IP, around Avi | no answer | default deny |
| 2 | The store's Service, around Avi | no answer | default deny |
| 3 | Through Avi, SQL injection | HTTP 403 | WAF |
| 4 | Through Avi, PHP injection | HTTP 403 | WAF |
| 5 | Through Avi, clean request | HTTP 200 | vDefend allows Avi to the store |
| 6 | East-west, a CVE-2021-41773 exploit to the users VM | connection reset | vDefend IDPS, prevent |

Check 6 belongs to the other security demo,
[vdefend-virtual-patching](../vdefend-virtual-patching). It is red
while the IDPS rule is in detect, the baseline, and violet while the
virtual patch is on. `flip.sh` does not change it.

Each check on the board shows the HTTP status code it got. A check that
gets through when it should not is red and shows its code, so with the
policy or the WAF off the attacks read HTTP 200, like the clean request.
Checks 1 and 2 are HTTP GETs to the store for this reason; no answer is
code 0.

## Before the demo

### What you need

- The `vcf` CLI, `kubectl`, `curl` and `jq`.
- A machine on the lab network that resolves `*.goad.gpu.set.lab`.
- A VCF Automation user in the `goad` org who is in the platform
  engineers' group. The group is admin of the project that holds Argo
  CD's namespace, so it may patch the Applications.
- The Grafana `admin` password, from a teammate.

### Make your vcf context

`flip.sh` patches the Argo CD Applications `music-store-platform` (the
default deny) and `music-store-apps` (the WAF). Argo CD's Applications are in the platform engineer's Supervisor Namespace,
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
   demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" status
   ```

   It prints whether each layer is there, the state of its
   Application, and the checks. Both layers must be present and
   checks 1 to 5 `1` before the demo starts. `vpatch`, check 6, is `0`
   unless the virtual patch is on:

   ```
   Default deny:   present; Application music-store-platform Synced, Healthy
   Avi WAF:        present; Application music-store-apps Synced, Healthy
   Pen test:       clean=1 phpi=1 pod=1 service=1 sqli=1 vpatch=0
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
   request let through. The path to the users VM, bottom left, is red:
   it stays red until the
   [vdefend-virtual-patching](../vdefend-virtual-patching) demo patches
   the VM.

2. Take the default deny out:

   ```bash
   demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" off deny
   ```

   ```
   Default deny: patched Application music-store-platform to take it out.
   Default deny: Argo CD taking it out. done (6s)
   Default deny: pen test checks pod service failing........ done (41s)
   ```

   The board's two paths around Avi turn red and run on to the store.
   The WAF paths do not change: the WAF is a separate layer.

3. Take the WAF out too:

   ```bash
   demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" off waf
   ```

   ```
   Avi WAF: patched Application music-store-apps to take it out.
   Avi WAF: Argo CD taking it out. done (6s)
   Avi WAF: pen test checks sqli phpi failing.............. done (72s)
   ```

   The SQL and PHP injections now reach the store and turn red. Every
   attack gets through; only the clean request is as it should be.

4. Put both back:

   ```bash
   demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" on all
   ```

   Within a minute every path is as in step 1. The board's history keeps
   the gap, which shows when each layer was out.

Each layer takes about a minute to show: a few seconds for Argo CD, then
up to two or three 30-second rounds of the checks. The script prints a
dot every 5 seconds while it waits. For a shorter demo, take one layer
out and put it back (`off deny`, then `on deny`), or both at once
(`off all`, then `on all`).

### How the flip works

Argo CD syncs both layers with self-heal on, so deleting them with
`kubectl` would be undone within seconds. Argo CD is not paused. `off`
adds kustomize patches to the layer's Application that take the layer
out of what Argo CD renders:

| Layer | Application | Patches |
|---|---|---|
| `deny` | `music-store-platform` | Delete the ClusterNetworkPolicy `music-store-default-deny` |
| `waf` | `music-store-apps` | Delete the L7Rule `metal-store-waf`, and remove the HTTPRoute filter that names it |

Argo CD prunes or updates the resources. `on` removes the patches, and
Argo CD puts the layer back. The Applications stay Synced throughout, and
nothing else in them changes.

## After the demo

Put both layers back if you did not, and check:

```bash
demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" on all
demos/pen-test-dashboard/flip.sh "$ARGO_CONTEXT" status
```

The patches are drift from the platform engineer's Terraform, which owns
the Applications. A `terraform apply` of `terraform/platform-engineer`
while a layer is off removes the patches and puts the layer back. Its
plan shows the patches as a change.

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
  DNS, looks like a drop. Run [pen-test-manual](../pen-test-manual) to
  see the real answer.
