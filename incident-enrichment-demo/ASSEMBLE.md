target: Goad org + Goad repo; nothing in Acme

# Step 0: PLAN AND WAIT FOR CAPTAIN APPROVAL

Before you create resources, edit manifests, deploy agents, or change any config in the Goad org or the Goad repo, do all of the following and then stop.

1. Inventory what already exists in VCFA org Goad. List spaces, apps, routes, services, Kubernetes namespaces, AgentMinder grants, and the music-store workloads. The cloud-admin terraform in this repo defaults the org resource name to `goad` and the display name to `GOAD`. Manifests in this package say org `Goad`, which is the name the Captain gave. If the live org identifier is not exactly `Goad`, stop and ask the Captain. Do not create a second org. Do not target org acme.
2. Confirm nothing you intend to add or change will break an existing resource. A name collision, a route already taken, a grant that would widen access, or a store namespace that is not the one already running is a risk. If there is any risk, stop and ask the Captain.
3. Write `PLAN.md` in this directory. One row per action. Columns: resource, target, command or change, order, rollback.
4. Wait until the Captain explicitly approves that `PLAN.md`.

Nothing executes without that approval. Filling a blank, pushing an app, mapping a route, and applying a grant are all execution.

The space is blank on purpose. `manifests/target.yml` sets `vcfa_org: Goad` and `vcfa_space: ""`. Do not invent a space name.

## What this package already contains

Assembly uses these parts. It does not rebuild them.

- Four agents (incident response, load balancer, Kubernetes, VCF): `agents/app.py`, system prompts in `agents/roles/*.md` (the push script writes `AGENTS.md` per app), skills in `skills/`, report schema `skills/schema/findings.schema.json`.
- Orchestrator in `orchestrator/`, including `reasoning_effort=none` on the model call, the load-balancer time limit in `orchestrator/enrich.py`, and the PII guardrail line in `pii-scrub/guardrail.py`.
- MCP doors: `mcp/k8s/` (Kubernetes), `mcp/vcf/` (VCF, including disk-latency replay switched by `VCF_DISK_LATENCY_REPLAY`, default off; the finding text stays a storage measurement), `avi-mcp/` (Avi). Tool grants are `manifests/agentminder/grants.yaml`.
- Tanzu manifests and the Pydantic agent buildpack (`python_buildpack` then `agent_buildpack`) in `manifests/tanzu/manifest.yml`. Push script: `manifests/tanzu/push.py`. It refuses to run while `GOAD_VCFA_SPACE` is empty.
- `demo.sh` commands: `start`, `enrich`, `deny`, `pii`, `restore`, `reset`. Store slowness is `fault-injection/`.
- Zammad client and the ticket title in `orchestrator/incident_title.py`. The helpdesk install notes are `zammad/`.
- Jev client: `orchestrator/jev.py` and `jev/WIRING.md`.
- AgentMinder grant list: `manifests/agentminder/grants.yaml`.
- `pii-scrub/` and `pii-scrub/chatguard/`.
- Grafana boards: `manifests/grafana/captain-incident-live.json` and `manifests/grafana/captain-demo-ready.json`.
- Topology: `topology/metal-music.json`.
- Demo script: `docs/demo-flow.md` and `docs/DEMO-RUNBOOK.md`.

The store workloads already live at `app/music-store/` in this repo. This package does not change those files.

## After the Captain approves PLAN.md

Do only the rows the Captain approved, in the order written there. The minimum stand-up is:

1. Fill the blanks in `BLANKS.md` in a secret store or in the approved manifests. Do not commit values.
2. Target VCFA org Goad and the space the Captain named. `cf target -o Goad -s "$GOAD_VCFA_SPACE"`.
3. Point the model endpoint at the house model through `pii-scrub`, with `reasoning_effort` left at `none` in `pii-scrub/app.py`.
4. Point `ZAMMAD_URL` and `ZAMMAD_TOKEN` at the Goad helpdesk.
5. Push the three MCP doors, then the four agents, with `manifests/tanzu/push.py`. Buildpacks are already in the manifest.
6. Push `pii-scrub`, then `pii-chat-guard`. Map the chat guard onto `POST /api/chat` of the incident response agent only after its health check is good.
7. Import the two Grafana boards and point their Infinity datasource at the incident-live app.
8. Replace the topology placeholders with the VMs, IPs, and datastore Step 0 inventoried.

## Smoke test

Run this only after the approved plan is in place.

1. `cf target` shows org Goad and the space from the approved plan, and `GET /health` on each MCP door returns 200.
2. `GET /health` on each of the four agents returns 200.
3. `./demo.sh start` opens one ticket titled "Metal Music Store slow: checkout and catalog pages taking 10+ seconds" and does not call the agents. The store answers HTTP 200 slowly.
4. In the incident response agent chat, send "pick up the latest incident ticket and enrich it". The ticket gains one enrichment note, and a repeat contact-details message shows the line that starts "PII guardrail: masked before the model saw it".
5. `./demo.sh restore` then `./demo.sh reset` leave the store answering HTTP 200 quickly, close the demo tickets, and leave the Incident live board empty.
