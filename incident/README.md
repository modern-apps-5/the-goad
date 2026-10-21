# Incident enrichment demo

Captain approved this package on 2026-10-14. This pull request adds the tree. It does not apply it, and it does not create anything in the org.

## Decisions in force

- Live org id is `goad`. Do not create a second org named `Goad`.
- Agents, MCP servers, pii-scrub, the store, Zammad, and Grafana run on VKS cluster `goad-store`. Not Cloud Foundry. `GOAD_VCFA_SPACE` stays empty. Do not run `manifests/tanzu/push.py`.
- Catalog database is container Postgres (`DB_HOST=postgres-service`). No DSM calls.
- `VCF_DISK_LATENCY_REPLAY=on`. `demo.sh start` applies the catalog query sleep. It does not start the disk-write loop.
- Ingress uses the existing service engine group `goad-se-group`. Do not create a service engine group. If `ingressClassName: avi` is rejected, stop.
- AgentMinder stays on the existing guest. New clients, later and only after a read: `py-goad-incident-response`, `py-goad-lb`, `py-goad-k8s`, `py-goad-vcf`. Stop if those names already exist or the endpoint does not answer.
- `goad-qwen` is class `best-effort-xlarge` (4 vCPU / 32 GiB), model `qwen2.5:32b`, context 4096. Expect about 20 to 40 minutes for one enrichment. Per-call ceiling is 900 seconds. `demo.sh enrich` stops at 60 minutes.

## What is not ready to apply

Images in `k8s/workloads.yaml` are `example.invalid` placeholders. Cluster `cluster/cluster.yaml` still has `REPLACE_WITH_STORE_SUPERVISOR_NAMESPACE`. Topology `topology/goad-music.json` is placeholders until a live read. Grafana boards are files only.

`ASSEMBLE.md` still describes the Cloud Foundry assembly order from the export. Where it conflicts with this file, this file wins.
