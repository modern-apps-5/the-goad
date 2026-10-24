# Goad: Tanzu Platform 11.0 on VKS

Draft, 2026-10-24. Docs only. This file authorizes no command against
any cluster. Goad only. Acme is read-only. The home lab is out. No
secret in git. Do not edit Wil's Terraform or `gitops/music-store`.

The existing foundation runbook stays
[`gitops/incident-demo/RUNBOOK.md`](../../gitops/incident-demo/RUNBOOK.md).
This draft is the move off that foundation.

## Order

Tanzu Platform 11.0 lands on a VKS cluster. Move only the agent
workloads that run today on the Tanzu foundation (org `Goad`, space
`metal-music-app-agentic-system`, `cf push` from
`gitops/incident-demo/tanzu-agents/`). Leave the music store where it
is.

## Do not touch

- `gitops/music-store` and `app/music-store`. That is the shop: VKS
  cluster `music-store`, the DSM catalog, the users VM, and the
  storefront. No manifest, Application, or cluster change.
- Zammad and Grafana. They already run on cluster `music-store`,
  namespace `incident-tools`. The agents call them by URL. They are
  not foundation apps.
- Qwen. Private AI `ModelEndpoint` with `routingName` `qwen` stays.
- AgentMinder. It already runs on VKS cluster `agentminder`. The
  product does not move. Only the three resource-server URLs follow
  the MCP routes, and only after the new routes answer.
- The nine apps on the current foundation. They stay up until a later
  cutover order. This draft does not stop them.
- Wil's org, platform-engineer, and AgentMinder Terraform.

## What moves

Pydantic AI agents (`python_buildpack`, then `agent_buildpack`):

- `incident-response-agent`
- `lb-diagnostic-agent`
- `k8s-diagnostic-agent`
- `vcf-diagnostic-agent`

The three diagnostic agents carry the `agentminder-sdk` sidecar. The
incident response agent does not. The sidecar moves with the app.

MCP tools (`python_buildpack`):

- `metal-k8s-mcp`
- `metal-avi-mcp`
- `metal-vcf-mcp`

The agent flow also needs these two apps from the same space:

- `metal-incident-live`, the orchestrator the chat calls
- `pii-scrub`, the model path

Manifests stay `tanzu-agents/manifest.yml`, `mcp.yml`, `live.yml`, and
`pii.yml`. Secrets stay `cf set-env`. Names and blanks stay in
`gitops/incident-demo/BLANKS.md`. Nothing from that list is written
here.

Push is still `python3 tanzu-agents/push.py`, aimed at the 11.0 API
once that API exists. Do not push into org `demo`. Do not push these
apps onto cluster `music-store`.

## Dedicated VKS cluster

Yes. 11.0 does not attach a cluster that already exists. The VMware
Kubernetes Service Provider tile provisions one and keeps it. Hub 11.0
states: "You cannot connect an existing VKS cluster." Each resource
segment then gets its own cluster: "each segment gets a dedicated
cluster." These nine apps are one segment, so they share that one new
cluster. They do not land on `music-store` or `agentminder`.

Sources:

- [Manage Kubernetes providers](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-hub/11-0/tnz-hub/foundations-kubernetes-provider-manage.html)
- [Foundation profiles](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-hub/11-0/tnz-hub/foundations-profiles-overview.html)
- [Tanzu Hub 11.0 release notes](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-hub/11-0/tnz-hub/release-notes.html)

Install is a tile in Foundation Core, not a Supervisor Service and not
a CLI. The tile is "VMware Kubernetes Service Provider on Tanzu
Platform." Apply Changes provisions the cluster. App workloads then
need the Applications on VKS profile (`tanzu-apps-on-vks`) and the
Resource Segment for Kubernetes tile, which runs Diego cells as pods
on the cluster the provider supplies. Ops Manager and Elastic
Application Runtime are 11.0. The Tanzu Hub installer OVA is Hub, not
this cluster.

- [Configure the VMware Kubernetes Service Provider tile](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-hub/11-0/tnz-hub/foundations-configure-vks-provider.html) (22 October 2026)
- [Tanzu Platform 11.0 release notes](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-platform/11-0/about-tnz-platform/release_notes.html) (11.0.0, 20 October 2026)
- [Resource Segment for Kubernetes overview](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/elastic-application-runtime/11-0/eart/k8s-resource-segment-overview.html)
- [Installing Resource Segment for Kubernetes](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/elastic-application-runtime/11-0/eart/installing-k8s-resource-segment.html)

Sizing, from the tile's Node Configuration. Production control plane
count is 3. Worker count defaults to 3. The default VM class for both
is `guaranteed-medium`: 2 vCPU and 8 GB RAM. `guaranteed` reserves the
whole amount. Storage class is the name of a class that already exists
in the Supervisor namespace. The doc does not name one. Every control
plane and worker node also gets a `/var/lib/tanzu` disk, default 64
GiB, on a second storage class you name. Other VM classes on the tile
run from `best-effort-xsmall` (2 vCPU, 2 GB) to `guaranteed-8xlarge`
(32 vCPU, 128 GB).

The workload cluster's Kubernetes version is not in these pages.

Supervisor and VCF, from the same tile and from
[Deploy a foundation](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/tanzu-hub/11-0/tnz-hub/foundations-deploy-foundation.html):

- Foundation Core is installed. The tile then reaches the Supervisor
  either through VCF Automation (VCF 9 with VCFA: API URL, org, refresh
  token, namespace) or through the Supervisor API (VCF 5.x on vSphere
  8, or VCF 9 without VCFA: API URL, vCenter SSO, namespace).
- A container registry: the Elastic Application Runtime internal
  registry, or an external OCI registry.
- The cluster must provide DNS. The resource segment's OpenTelemetry
  collector is optional.
- Foundation Core itself can be vended onto vSphere 8.0 or later, VCF
  Automation 9.0 or 9.1, or vSphere Supervisor 9.0 or later. Vending
  onto VCF 9 or a Supervisor is Tech Preview. A Supervisor target needs
  Namespace Management API v2, NSX VPC, and VCF Networking with VPC. One
  namespace maps to one foundation. Hub creates the content library
  `tanzu-system-supervisor` if it is missing.

## Telemetry

The Diego blocker is dropped. On the current foundation, app telemetry
leaves through the Elastic Application Runtime OpenTelemetry collector
on the foundation VMs. Turning that collector on is a tile System
Logging change, or a BOSH `runtime-config` on the Diego cell. This
move does not do either. There is no Diego cell on the VKS runtime, so
that collector is not on the path and it is not a prerequisite.

11.0 still exports logs and metrics for a workload scheduled on VKS.
The agent view shipped with 11.0 is the agentic performance dashboard,
the agentic trace detail, and structured logs: prompt, token use,
latency, and MCP tool calls. That is the product statement from the
2026-10-23 Tanzu Platform 11.0 announcement. It is not a Goad wiring
diagram. Grafana in `incident-tools` and the VKS observability add-on
(issue 11) are not assumed to be that path.

## When a later order says to execute

1. The runtime is the VKS cluster the VKS Provider tile provisions.
   It is not `music-store`, not `agentminder`, and not an Acme or
   home-lab cluster. Record the API and the apps domain. Do not reuse
   `api.sys.tp.gpu.set.lab` or `*.apps.tp.gpu.set.lab` unless that
   order says they moved.
2. `cf target` the 11.0 API, org `Goad`, space
   `metal-music-app-agentic-system`. Create the org and space if they
   are absent.
3. Push the nine apps above. One app at a time. Env from the blanks.
   The script must not print secrets.
4. `GET /health` is HTTP 200 on all nine. `GET /` on
   `incident-response-agent` is the chat page.
5. Point AgentMinder resource servers `goad-k8s-mcp`, `goad-avi-mcp`,
   and `goad-vcf-mcp` at `https://metal-*-mcp.<apps-domain>/mcp`.
6. In the chat, send `pick up the latest incident ticket and enrich
   it`. Success is the same bar as the current runbook: steps in the
   chat, one Grafana annotation row per step, one Zammad note whose
   root cause is storage latency. `/health` 200 is not success.
7. Leave the old foundation apps running until a separate stop order.

## Open questions

1. Resolved. The VKS runtime is the VMware Kubernetes Service Provider
   tile in Foundation Core, plus the Applications on VKS profile and
   the Resource Segment for Kubernetes tile. It is not a Supervisor
   Service and not a CLI install. The Hub OVA installs Hub, not this
   cluster. See Dedicated VKS cluster.
2. Resolved. The tile provisions a new cluster. An existing cluster
   cannot be connected, so the runtime is not `music-store` and not
   `agentminder`. One resource segment, one cluster, for these nine
   apps.
3. API endpoint and apps domain for that runtime.
4. Are `python_buildpack`, `agent_buildpack`, and the
   `agentminder-sdk` sidecar present on 11.0-on-VKS in this lab?
5. Resolved for the platform. Elastic Application Runtime 11.0 release
   notes say container-to-container networking, network policies, and
   internal route resolution work on VKS cells as they do on Diego
   cells, and the policies become Kubernetes NetworkPolicy objects.
   [Elastic Application Runtime 11.0 release notes](https://techdocs.broadcom.com/us/en/vmware-tanzu/platform/elastic-application-runtime/11-0/eart/runtime-rn.html).
   The Diego bosh-dns empty-answer failure is not carried forward.
   Whether this lab's chat still needs the `apps.internal` hostname
   map is untested, and this draft does not test it.
6. Where do 11.0-on-VKS logs, metrics, and agent traces land in Goad?
   The resource-segment collector is optional. Platform UI only, an
   OTLP endpoint, the VKS observability add-on, or Grafana in
   `incident-tools`? No destination is chosen.
7. Are the AgentMinder resource-server URL updates in the same change
   as the push, or only after the new `/health` checks pass?
8. When are the nine apps on the existing foundation stopped?
9. May Acme be read as a layout reference? It stays read-only either
   way. Nothing is copied into Goad without a separate order.
10. Which Kubernetes version does the VKS Provider tile put on the
    cluster? The 11.0 tile page, the resource-segment pages, and the
    platform release notes do not say.
11. Which tile mode matches this lab, VCFA or direct Supervisor, and
    does this Supervisor meet the vending rules (Supervisor 9.0 or
    later, Namespace Management API v2, VCF Networking with VPC) if
    Foundation Core is placed on it? Not checked. No cluster command.
12. Which existing Supervisor storage class names go in the tile's
    Storage Class and Ephemeral Disk Storage Class fields?
