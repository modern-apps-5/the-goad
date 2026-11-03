# Storage troubleshooting: from a slow checkout to a vSAN policy

A browser demo, as the platform engineer and then the ops engineer. The
shop's add to cart and checkout are slow and fail, while the catalog is
fast. Follow it down from the app, through VCF Operations platform
observability, to the VKS worker VM, its host, and vSAN, and find the
cause: the cart and order disks were moved to a storage policy with an
IOPS limit.

The point: one tool from the app to the disk. The platform engineer sees
the pods are healthy and wait on storage, and an alert under the VKS cluster
names the VM; the ops engineer follows that VM down to the vSAN policy,
with no hand-off ticket and no guessing.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The symptom | The shop |
| 0:40 | 2. The pods wait on storage | VCF Operations, platform observability |
| 1:40 | 3. The VKS cluster's alert | VCF Operations, VKS cluster `music-store` |
| 2:20 | 4. The worker VM's disks | VCF Operations, the worker VM |
| 3:10 | 5. Not the host, not vSAN | VCF Operations, the VM's topology |
| 3:50 | 6. The disks' policy | VCF Operations, the VM's properties |
| 4:20 | 7. The cause | vCenter, the storage policy |

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- A VCF Automation user in org `goad` with access to the project that
  holds the namespaces, and the `vcf` CLI.
- A VCF Operations user that can see the cluster `MGMT-cl01` and the
  Supervisor.
- A vCenter user that can create storage policies and edit VM disks in
  `MGMT-cl01`.
- `kubectl` and [`uv`](https://docs.astral.sh/uv/).

### The vcf context

`fault.sh` reads the music store cluster's kubeconfig and the CNS
volumes from the Supervisor Namespace `music-store-<suffix>`. You need a
vcf context for that namespace, logged in as yourself.

1. Make a context for the org. The name is yours; `goad` is used below.
   Use an API token that you made in VCF Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

   The vcf CLI makes one more context for each namespace you can use,
   named `<context>:<namespace>:<project>`.

2. Find the one for the music store:

   ```bash
   vcf context list | grep ':music-store-'
   ```

   For example `goad:music-store-8q8l6:default-project`. It is the
   `<store context>` below.

### The alert and the dashboard, once

The demo uses a platform observability dashboard and a VCF Operations
alert on the VKS cluster's node VMs. The cloud admin's Terraform root
[terraform/cloud-admin/ops](../../terraform/cloud-admin/ops) makes them,
and the `cloud-admin` workflow applies it. Before a run, check in VCF
Operations that:

- The dashboard "GOAD: node disk latency" is listed in platform
  observability.
- The alert definition "VKS node VM has a virtual disk with high write
  latency" is Activated in the default policy.

### Start the fault

At least 15 minutes before the demo, so VCF Operations has collected the
new latency and raised the alert:

```bash
export VC_HOST=vc01.gpu.set.lab VC_USER=<your vCenter user>
demos/storage-troubleshooting/fault.sh <store context> start
```

It asks for your vCenter password, then prints each disk it moved:

```
pvc-4721bd97-…  music-store-workers-6xtl4-wnr4j-8n8n5  Hard disk 3  policy: Archive Tier - IOPS Limited
pvc-f4cc848c-…  music-store-workers-6xtl4-wnr4j-8n8n5  Hard disk 2  policy: Archive Tier - IOPS Limited
```

Note the worker VM; steps 2 to 6 use it.
Eight shoppers then start in the cluster, in namespace `shoppers`.

Check it took:

```bash
demos/storage-troubleshooting/fault.sh <store context> status
```

The shoppers' log lines show `add_to_cart` and `pay` at several seconds,
some with status `500`, and `catalog` under a second.

### Browser tabs

1. The shop, `https://music.goad.gpu.set.lab`.
2. VCF Operations, `https://ops01.gpu.set.lab`.
3. vCenter, `https://vc01.gpu.set.lab`.

## Run the demo

### 1. The symptom (0:00)

Tab 1, the shop.

**Show**

- The catalog loads fast.
- Add an album to the cart: it spins for seconds, or fails.

**Why**: users report "checkout is broken". The catalog works, so the
shop is up; something under the cart is slow.

### 2. The pods wait on storage (0:40)

Tab 2, VCF Operations, platform observability, the dashboard "GOAD: node
disk latency", source `music-store`.

**Show**

- The shop's pods: CPU and memory low and flat.
- Slowest disk: red, over 30 ms.
- Write latency per disk: one agent's `sdb` and `sdc`, the PVC disks,
  far above every other disk, including its own `sda`.
- Write IOPS per disk: the same two flat at a ceiling of about 10.

**Why**: nothing is out of CPU or memory. Two PVC disks on one node are
slow and capped while the node's own disk is fine. Latency up with IOPS
flat is a limit, not load.

### 3. The VKS cluster's alert (1:40)

VCF Operations, Inventory, VKS Cluster, `music-store`, Alerts.

**Show**

- The cluster's own alerts: none. Its metrics look fine.
- **INCLUDE**: add descendants. The alert "VKS node VM has a virtual
  disk with high write latency" appears, on the worker VM.
- The recommendation: compare the VM's disks, then check the slow
  disk's storage policy.

**Why**: the cluster looks healthy, but one of its node VMs does not.
The platform engineer hands ops one object, not a hunch.

### 4. The worker VM's disks (2:20)

Click the VM alert, then its VM. Alerts: the symptom names the disk
instance, `scsi0:1` or `scsi0:2`, and its latency. Then Metrics, Virtual
Disk, write latency for `scsi0:0`, `scsi0:1` and `scsi0:2`.

**Show**

- `scsi0:1` and `scsi0:2`, the PVC disks: write latency from 0 to
  over 100 ms when the fault started.
- `scsi0:0`, the OS disk on the same VM: near 0.

**Why**: one VM, one datastore, but only two of its disks are slow. A
host or vSAN problem would slow all three.

### 5. Not the host, not vSAN (3:10)

The VM's topology: VM, host, cluster `MGMT-cl01`, datastore
`MGMT-cl01-ds-vsan01`.

**Show**

- The host: CPU, memory and network normal.
- The vSAN datastore: latency normal, healthy.
- The other VMs on the host: normal disk latency.

**Why**: the hardware and vSAN serve every other workload fine. The
problem is something only these two disks have.

### 6. The disks' policy (3:50)

The VM, Properties, Virtual Disk.

**Show**

- `scsi0:1` and `scsi0:2`: storage policy `Archive Tier - IOPS
  Limited`.
- `scsi0:0`: `MGMT-cl01 - Optimal Datastore Default Policy - AutoRAID`.

**Why**: the two slow disks are the two on a different policy.

### 7. The cause (4:20)

Tab 3, vCenter, Policies and Profiles, VM Storage Policies, `Archive
Tier - IOPS Limited`.

**Show**

- The vSAN rule: IOPS limit 10.
- VM Compliance: the worker VM's two PVC disks.

**Why**: the disks were moved to an archive tier meant for cold data.
From the user's report to the policy, without leaving the VCF tools or
opening a ticket between teams.

## After the demo

Put the disks back on their StorageClass's policy and stop the shoppers:

```bash
demos/storage-troubleshooting/fault.sh <store context> stop
```

It prints each disk on `MGMT-cl01 - Optimal Datastore Default Policy -
AutoRAID`. Add an album to the cart: it takes under a second. The policy
`Archive Tier - IOPS Limited` stays in vCenter for the next run; no disk
uses it.

## Troubleshooting

- **`Context … has no namespace`**: the context is the parent context.
  Use the one that ends in `music-store-<suffix>:default-project`.
- **`No resource pool music-store-<suffix> in vCenter`**: your vCenter
  user cannot see the namespace's resource pool. Use a user with read
  access to `MGMT-cl01`.
- **`Not attached to a VM`**: the cart or order pod is not running, so
  its disk is not attached. Check `music-store-apps` in Argo CD.
- **The shop is fast after start**: VCF Operations and the shoppers need
  a minute. Run `status`; if the disks show the archive policy and the
  shoppers' requests are under a second, set `IOPS_LIMIT=5` and run start
  again.
- **The shop is down, not slow**: too many shoppers for the limit. Scale
  them down: `kubectl -n shoppers scale deploy/shoppers --replicas=4` on
  the music store cluster, or run start with a higher `IOPS_LIMIT`.
- **VCF Operations shows no change, or no alert**: it collects every
  five minutes, and the alert needs one collection over 30 ms. Start the
  fault 15 minutes before the demo. If the VM's latency is high and there
  is still no alert, check that the alert is on. It comes from
  `terraform/cloud-admin/ops`. A new alert is deactivated in Base
  Settings, and the root activates it in the default policy. If the VKS cluster has another policy (its
  **POLICY** button), edit that policy, Alerts and Symptoms, and set the
  alert to Activated.
