# Pen test by hand: an attacker pod next to the store

One of two pen test demos. In this one you start an attacker pod in the
music store's own namespace and run five attacks from it, with the
results in your terminal. The other,
[pen-test-dashboard](../pen-test-dashboard), shows the same checks on the
Grafana board and turns the default deny off and on.

What it shows (decision 49,
[docs/security-architecture.md](../../docs/security-architecture.md)):

- The Antrea default deny in `gitops/music-store-platform` drops traffic
  that goes around Avi, even from a pod in the store's own namespace.
- The Avi WAF, attached to the shop's route by the L7Rule
  `metal-store-waf` in `gitops/music-store-apps`, answers 403 to SQL and
  PHP injection, and lets a clean request through.

Personas: the platform engineer runs it; the policies it tests are the
security admin's, the developer's and the platform engineer's.

| File | What it is |
|---|---|
| `run.sh` | Puts the checks in a ConfigMap, starts the attacker pod, and runs the checks in it. `--delete` removes it all. |
| `connectivity-check.sh` | The five checks. Runs inside the pod. |
| `attacker.yaml` | The attacker pod `attacker` in namespace `music-store`, on `alpine/k8s`, with no shop labels, and a Role that lets it look up the store pod's IP. |

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

- The `vcf` CLI and `kubectl`.
- A VCF Automation user in the `goad` org who is in the platform
  engineers' group, which is admin of the project that holds the music
  store's namespace.

### Get kubectl on the music store cluster

`run.sh` runs `kubectl` against the VKS cluster `music-store`, with the
current context. That cluster's kubeconfig comes from its Supervisor
Namespace, named `music-store-<suffix>`.

1. Make a vcf context for the org, if you have none. The name is yours;
   `goad` is used below. Use an API token that you made in VCF
   Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

2. Use the context of the music store's namespace, and get the cluster's
   kubeconfig:

   ```bash
   vcf context list | grep ':music-store-'      # e.g. goad:music-store-8q8l6:default-project
   vcf context use goad:music-store-<suffix>:default-project
   vcf cluster kubeconfig get music-store
   ```

   This adds a kubectl context for the cluster to your kubeconfig.

3. Switch to it and check it:

   ```bash
   kubectl config use-context <the context it added>
   kubectl -n music-store get pods
   ```

   The store, cart, order and chat pods are running.

## Run the demo

1. Run the checks:

   ```bash
   demos/pen-test-manual/run.sh
   ```

   It starts the pod `attacker`, waits until it is ready, and runs the
   five checks in it. The results match the table above: the two paths
   around Avi get no answer, the two attacks through Avi get 403, and
   the clean request gets 200.

2. To show where the drops happen, follow the Antrea policy log on the
   node that runs the store, and run step 1 again:

   ```bash
   kubectl -n music-store get pod -l service-name=store -o wide      # the node
   kubectl -n kube-system get pod -l component=antrea-agent -o wide  # its agent
   kubectl exec -n kube-system <antrea-agent-pod> -c antrea-agent -- \
     tail -f /var/log/antrea/networkpolicy/np.log
   ```

   Each drop is a line for `music-store-default-deny`.

`run.sh` reuses the pod if it is already there, so step 1 can be run as
often as you like.

## After the demo

Remove the pod. It stays until you do:

```bash
demos/pen-test-manual/run.sh --delete
```

This removes the pod, its ServiceAccount, Role and RoleBinding, and the
ConfigMap `pen-test-script`. Check:

```bash
kubectl -n music-store get pod attacker      # NotFound
```

## Troubleshooting

- **`You must be logged in to the server`** on `vcf` commands: the vcf
  session expired. `vcf context refresh goad`, then run the command
  again.
- **The pod is not ready after 120 seconds**: the image did not pull.
  `kubectl -n music-store describe pod attacker` shows why.
- **Checks 3 to 5 fail to resolve the shop's name**: the cluster cannot
  resolve `music.goad.gpu.set.lab`. Give the Gateway's address:

  ```bash
  VIP=$(dig +short @172.21.0.90 music.goad.gpu.set.lab A) demos/pen-test-manual/run.sh
  ```

- **Checks 3 and 4 answer 200**: the WAF policy is in detection mode.
  Set `System-WAF-Policy` to enforcement in Avi.
