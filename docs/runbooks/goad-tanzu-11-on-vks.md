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

1. Confirm the 11.0 runtime is a VKS cluster that is not
   `music-store` and not an Acme or home-lab cluster. Record the API
   and the apps domain. Do not reuse `api.sys.tp.gpu.set.lab` or
   `*.apps.tp.gpu.set.lab` unless that order says they moved.
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

1. Tile or VKS install. Does an Ops Manager tile for 11.0 target a VKS
   cluster in Goad, or is the supported landing the 11.0 OVA into the
   VCF org, or a supervisor service on VCF 9.1? The announcement says
   the platform is deployed as an OVA into a VCF org and that a
   workload can be scheduled onto VKS or VMs. It does not say the
   tile's Diego collector config applies to VKS. Unresolved. Do not
   pick one.
2. Which VKS cluster receives the 11.0 runtime? Not `music-store`.
   Cluster `agentminder` already runs AgentMinder. Undecided.
3. API endpoint and apps domain for that runtime.
4. Are `python_buildpack`, `agent_buildpack`, and the
   `agentminder-sdk` sidecar present on 11.0-on-VKS in this lab?
5. Do `apps.internal` and app-to-app network policy behave on the VKS
   runtime the way the chat needs? The Diego bosh-dns empty-answer
   failure is a current-foundation fact. It is not carried forward.
6. Where do 11.0-on-VKS logs, metrics, and agent traces land in Goad?
   Platform UI only, an OTLP endpoint, the VKS observability add-on,
   or Grafana in `incident-tools`? No destination is chosen.
7. Are the AgentMinder resource-server URL updates in the same change
   as the push, or only after the new `/health` checks pass?
8. When are the nine apps on the existing foundation stopped?
9. May Acme be read as a layout reference? It stays read-only either
   way. Nothing is copied into Goad without a separate order.
