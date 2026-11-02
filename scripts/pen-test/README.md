# Pen test: the shop is reachable only through the Avi WAF

An attacker pod inside namespace `music-store` of the VKS cluster
`music-store` tries to reach the shop's front end around Avi and through
it. It shows two layers working together (decision 49):

- The Antrea default deny in `gitops/music-store-platform` drops traffic
  that goes around Avi: the store pod's IP and its Service.
- The Avi WAF, attached to the shop's route by the L7Rule
  `metal-store-waf` in `gitops/music-store-apps`, answers 403 to SQL and
  PHP injection, and lets a clean request through.

| File | What it is |
|---|---|
| `connectivity-check.sh` | The five checks. Runs inside the pod. |
| `attacker.yaml` | The pod, on `alpine/k8s`, and a Role that lets it look up the store pod's IP. |
| `run.sh` | Puts the script in a ConfigMap, starts the pod, and runs the check. |

## Run

With `kubectl` on the VKS cluster `music-store`:

```bash
scripts/pen-test/run.sh
```

| # | Check | With the policy and the WAF |
|---|---|---|
| 1 | The store pod's IP | no answer, dropped by the default deny |
| 2 | The store's Service | no answer, dropped by the default deny |
| 3 | Through Avi, SQL injection | HTTP 403 from the WAF |
| 4 | Through Avi, PHP injection | HTTP 403 from the WAF |
| 5 | Through Avi, clean request | HTTP 200 |

The shop's name resolves through DNS. If the cluster cannot resolve it,
give the Gateway's address:

```bash
VIP=$(dig +short @172.21.0.90 music.goad.gpu.set.lab A) scripts/pen-test/run.sh
```

The drops show in the Antrea policy log on the node that runs the store:

```bash
kubectl exec -n kube-system <antrea-agent-pod> -c antrea-agent -- \
  tail -f /var/log/antrea/networkpolicy/np.log
```

Remove the pod afterwards:

```bash
scripts/pen-test/run.sh --delete
```

## Flip the default deny for a demo

`flip.sh` turns the default deny off and on without a commit, so the
board "Pen test" changes on cue:

```bash
NAMESPACE=platform-9pq9n scripts/pen-test/flip.sh sup-gpu off      # checks 1 and 2 turn red
NAMESPACE=platform-9pq9n scripts/pen-test/flip.sh sup-gpu on       # and green again
NAMESPACE=platform-9pq9n scripts/pen-test/flip.sh sup-gpu status
```

The first argument is a context that reaches the Supervisor Namespace of
the Argo CD Applications; `NAMESPACE` is that namespace, if the context
does not already point at it. Argo CD is not paused. `off` adds a
kustomize patch to the Application `music-store-platform` that deletes
`music-store-default-deny`, and Argo CD prunes it; `on` removes the
patch. Each takes about a minute: a few seconds for Argo CD, then up to
two 30-second rounds of the checks. The WAF checks do not change.

The patch is drift from the platform engineer's Terraform. Run `on`
after the demo; a platform engineer apply also puts the policy back.

## Before and after

To show the attacks getting through first, take both layers out and put
them back. Argo CD heals anything deleted by hand, so do it in git:

1. Commit a change that removes `network-policy.yaml` from
   `gitops/music-store-platform/kustomization.yaml` and
   `metal-store-waf-l7rule.yaml` from
   `gitops/music-store-apps/kustomization.yaml`. Once Argo CD syncs, all
   five checks answer 200.
2. Revert that commit. Once Argo CD syncs, the checks give the table
   above.

## The board

The same five checks run all the time from namespace `pen-test`
(`gitops/music-store-platform/pen-test.yaml`), every 30 seconds. The
Grafana board "Pen test" on the platform tools cluster draws them as
the attacker's paths to the store, green or red, with their history
under it. During the before and after, the history shows when each
layer went out and came back.

Checks 1 and 2 are TCP connections, not HTTP requests: a pass is no
connection. A probe that fails for another reason, such as DNS, also
shows as dropped. `run.sh` remains the check to run by hand.
