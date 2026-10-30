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
