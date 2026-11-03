# Cloud admin: VCF Operations content

The cloud admin's VCF Operations content for the lab: platform
observability dashboards and alerts. It is not a stage: it needs nothing
the org roots make, and they need nothing from it. The state is
`goad-cloud-admin-ops`.

No provider covers this, so every object is a TerraCurl call to the VCF
Operations API, with a fresh login on each plan, apply, and destroy.

| File | What it creates |
|---|---|
| `dashboards.tf` | One platform observability dashboard (Explore Charts) for each `dashboards/*.json`. |
| `alerts.tf` | The alert "VKS node VM has a virtual disk with high write latency", its two symptoms and its recommendation, and turns the alert on in the default policy. |

## Dashboards

Each file in `dashboards/` is a Grafana dashboard. In VCF Operations the
viewer picks the cluster, the Source, so a dashboard is not tied to one.

| File | Dashboard | Shows |
|---|---|---|
| `node-disk-latency.json` | GOAD: node disk latency | Write IOPS, latency and queue per node and disk of a VKS cluster, next to the music store's pods. The built-in I/O dashboard adds every node's disks together, so one slow disk does not show there. |

To add a dashboard, put its JSON in `dashboards/` and apply. It must have:

- `schemaVersion` 42 or later. Grafana 10 and later write this; an older
  export fails to import.
- A `uid` that no other imported dashboard has.
- Queries in PromQL against the datasource `PBFA97CFB590B2093`, VCF
  Operations' own. Metric names are the OpenTelemetry ones with dots, for
  example `system.disk.operations` or `k8s.pod.cpu.usage`.
- Only the panel types `stat`, `text`, `table`, `timeseries`, `gauge`,
  `bargauge`, `piechart` and `row`. Others import as empty placeholders.

Build and test the queries in VCF Operations, Explore Charts, against a
cluster, then export the dashboard JSON.

## The alert

It fires on a VKS node VM, a VM with a `KubernetesNode` child, when one of
its virtual disks has write latency over `node_disk_latency_threshold_ms`
(30 by default) for one collection, five minutes. The symptom names the
disk, so a slow PVC disk shows apart from the node's OS disk. VCF
Operations' own VM latency symptoms wait three collections and raise no
alert by themselves. Open a VKS cluster, Alerts, and include descendants
to see it there.

A new alert definition is deactivated in Base Settings, so every policy
inherits it off. This root turns it on in the default policy. If a VKS
cluster's objects have another policy, turn the alert on in that one too.

## What it does not see

The API has no call to update a dashboard, and this root reads nothing
back. So:

- A changed file or alert makes a new object and deletes the old one.
- A change made in the VCF Operations UI is not seen, and the next apply
  does not put it back.

## Apply

```sh
cp terraform.tfvars.example terraform.tfvars   # ops_password
cp backend.hcl.example backend.hcl             # the shared Gitea token
terraform init -backend-config=backend.hcl
terraform apply
```

The `cloud-admin` workflow runs this root as its `ops` job.
