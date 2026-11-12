# vDefend virtual patching

An exploit for a known CVE reaches the music store's users VM from
inside the VKS cluster, east-west, where the Avi WAF never sees it.
vDefend Distributed IDPS on the VM's vNIC sees it and logs it. Turn on
prevention for that VM, and the same request is reset before it reaches
the VM. No change to the VM, no code change, and no agent.

The exploit is CVE-2021-41773, the Apache 2.4.49 path traversal. The
users VM does not run Apache, so it answers 404. That 404 is the point:
the request reached the workload.

| File | What it is |
|---|---|
| `attack.sh` | Starts the pod `vpatch-attacker` and sends a clean request and the exploit to the users VM. `--delete` removes the pod. |
| `patch.sh` | `on`, `off` or `status`: the IDPS rule's action in NSX Manager, and the IDPS events. |
| `attacker.yaml` | The pod `vpatch-attacker` in namespace `music-store`, on `alpine/k8s`, with no shop labels and no API access. |

## Steps

| Step | Screen |
|---|---|
| 1. The workload | VCF Automation, `music-store-<suffix>` |
| 2. IDPS on the VM | NSX Manager, project `goad`, Distributed Rules |
| 3. The exploit lands | Terminal |
| 4. Detected | NSX Manager, Events |
| 5. Virtual patch | Terminal, then NSX Manager, then Grafana |
| 6. The exploit is blocked | Terminal, then NSX Manager, Events |
| 7. It's code | GitHub |

## Before the demo

### What you need

- `kubectl`, the `vcf` CLI, `curl` and `jq`.
- A VCF Automation user in org `goad`, in the platform engineers' group,
  for the music store cluster's kubeconfig.
- An NSX Manager user who may edit the IDPS policy of the NSX project
  `goad`, and its password.
- The lab's IDPS state: DFW and IDPS on for the vSphere cluster
  ([docs/build.md](../../docs/build.md), Before you start), and the
  `security-admin` workflow applied, so the IDPS policy `music-users`
  exists in project `goad`.

### Get kubectl on the music store cluster

1. Make a vcf context for the org, if you have none. Use an API token
   that you made in VCF Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

2. Use the context of the music store's namespace, and get the
   cluster's kubeconfig:

   ```bash
   vcf context list | grep ':music-store-'      # e.g. goad:music-store-8q8l6:default-project
   vcf context use goad:music-store-<suffix>:default-project
   vcf cluster kubeconfig get music-store
   kubectl config use-context <the context it added>
   ```

### Set the NSX login for patch.sh

```bash
export NSX_HOST=nsx01.gpu.set.lab NSX_USER=<your NSX user>
read -rs NSX_PASSWORD && export NSX_PASSWORD
# If your trust store does not hold the lab CA:
openssl s_client -connect "$NSX_HOST:443" -showcerts </dev/null 2>/dev/null |
  awk '/BEGIN CERT/,/END CERT/' > nsx.pem
export NSX_CACERT=$PWD/nsx.pem
```

### Check the lab

```bash
demos/vdefend-virtual-patching/patch.sh status   # users-vm-inbound: DETECT
demos/vdefend-virtual-patching/attack.sh         # clean 200, exploit 404
```

The second command also starts the attacker pod, so step 3 is quick.

### Browser tabs

1. VCF Automation, `https://auto.gpu.set.lab`, org `goad`, Supervisor
   Namespaces.
2. NSX Manager, `https://nsx01.gpu.set.lab`, project `goad` in the
   project picker at the top, Security, IDS/IPS & Malware Prevention.
3. GitHub: `terraform/security-admin/idps.tf`.
4. Grafana, `http://grafana.goad.gpu.set.lab/d/goad-pen-test`, as
   `admin`. The bottom-left path is pen test check 6: the same exploit
   from namespace `pen-test`, every 30 seconds. Red while the rule is in
   Detect.

## Run the demo

### 1. The workload

Tab 1, namespace `music-store-<suffix>`, Virtual Machines.

**Show**

- VM `music-users`: the shop's users service, running, its IP.

**Why**: a VM the shop depends on. Patching it means a change window;
the exploit for the CVE is public today.

### 2. IDPS on the VM

Tab 2, Distributed Rules.

**Show**

- Policy `music-users`, rule `users-vm-inbound`: applied to group
  `music-users`, mode Detect Only.
- Group `music-users`: matched on the tag `app|users-service`, the VM's
  own label. No IP address.
- Profile `music-users`: critical, high and medium signatures, and the
  six CVE-2021-41773 signatures forced on.

**Why**: IDPS runs in the hypervisor on the VM's vNIC. It sees east-west
traffic that never passes a perimeter firewall or the WAF.

### 3. The exploit lands

```bash
demos/vdefend-virtual-patching/attack.sh
```

```
clean      /health  HTTP 200
exploit    /cgi-bin/.%2e/.%2e/.%2e/.%2e/etc/passwd  HTTP 404
```

**Show**: the exploit gets an answer from the VM.

**Why**: an attacker with a foothold in the cluster reaches the VM.
Network policy allows the flow, because the shop needs it.

### 4. Detected

Tab 2, Events. Refresh.

**Show**

- `ET EXPLOIT Apache HTTP Server 2.4.49 - Path Traversal Attempt
  (CVE-2021-41773) M2`, and the NSX signature for the same CVE.
- Open one: the VM `music-users`, the source, the CVE and its CVSS.

**Why**: the security team sees the attack, and knows which workload and
which CVE.

### 5. Virtual patch

```bash
demos/vdefend-virtual-patching/patch.sh on
```

```
users-vm-inbound: DETECT_PREVENT
```

Tab 2, Distributed Rules, refresh.

**Show**: rule `users-vm-inbound` is now Detect & Prevent.

Tab 4, within a minute.

**Show**: the bar `vDefend IDPS` turns from Detect only to Detect &
Prevent, the path to the users VM stops at it and turns violet, and
check 6 in the history turns from red to violet.

**Why**: the patch is a policy on the VM's vNIC. Nothing on the VM
changes, and it takes effect in seconds.

### 6. The exploit is blocked

```bash
demos/vdefend-virtual-patching/attack.sh
```

```
clean      /health  HTTP 200
exploit    /cgi-bin/.%2e/.%2e/.%2e/.%2e/etc/passwd  connection reset
```

Tab 2, Events, refresh.

**Show**

- The exploit is reset. The clean request still gets 200.
- The same signatures with new occurrences.

**Why**: the VM is protected until it is patched, and the shop keeps
working.

### 7. It's code

Tab 3, `terraform/security-admin/idps.tf`.

**Show**

- The group, the profile with the CVE's signatures, and the rule.
- The rule's action in git is `DETECT`.

**Why**: the security admin's IDPS policy is in git and applied by the
`security-admin` workflow, like the rest of vDefend. Making the patch
permanent is a one-line pull request.

## After the demo

```bash
demos/vdefend-virtual-patching/patch.sh off      # users-vm-inbound: DETECT
demos/vdefend-virtual-patching/attack.sh --delete
```

Check: `patch.sh status` says `DETECT`, and
`kubectl -n music-store get pod vpatch-attacker` says NotFound.

If you forget `off`, the next `security-admin` apply puts `DETECT` back.

## Troubleshooting

- **`patch.sh`: 404 on the rule.** The IDPS policy is not applied. Run
  the `security-admin` workflow with apply.
- **`patch.sh`: 403.** Your NSX user cannot edit the goad project's IDPS
  policy.
- **`patch.sh`: certificate error.** Set `NSX_CACERT`, see Before the
  demo.
- **Events before step 3.** Pen test check 6 sends the exploit every 30
  seconds, so the events are already there. Their source is the
  `pen-test` probe; `attack.sh` adds more.
- **No event in step 4.** IDPS is off for the vSphere cluster, or the
  group `music-users` has no member: in NSX Manager, open the group's
  members. The VM must carry the label `app: users-service`
  (`gitops/music-store/users-vm.yaml`).
- **The exploit times out instead of 404.** The users VM or its load
  balancer is down. Check `/health` gets 200 first.
