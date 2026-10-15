# Agentic Incident Enrichment: Demo Flow (VCF Lab)

**Goal:** show a real incident go from alert to an enriched, routed ticket with no human doing the triage. A cloud decision model (Jev) makes the decision, and house models write the enrichment.

## The cast: who does what
| Part | Role |
|---|---|
| **Metal Music Store** (store 5000/Postgres, cart 5002, orders 5001, users-service) on VCF lab VKS | The production app that breaks |
| **Traffic generator** (Selenium, 5004) | Keeps real shopper traffic flowing, so the failure shows up in metrics and logs |
| **Fault injection** (scripted: scale Postgres to 0, or add latency to cart) | Causes the incident on cue |
| **Monitoring** (app health checks plus VCF/k8s events and pod logs) | Spots the failure and opens a ticket in Zammad |
| **Zammad** | Ticketing system. Holds the incident: first bare, then enriched |
| **Orchestrator agent** (the harness) | Gathers evidence (logs, metrics, k8s events, recent changes, similar past tickets) and builds one decision question: "here is the evidence; options A/B/C/D, which one?" |
| **Jev** (TypeSafe, cloud) | The decider. It takes the question and options and returns its choice, such as root-cause class, severity, owning team or next action, with reasons. It never talks to systems directly |
| **Qwen on DGX** (house model) | Writes the enrichment: summary, likely cause, evidence and suggested fix |
| **Human (on-call)** | Opens the ticket, reads it, approves or overrides the action |

## The flow and what's on screen
1. **Healthy baseline.** Store UI plus the traffic generator running. *Screen:* store page, with Grafana or pod status all green.
2. **Break it.** Run the fault script (for example, Postgres scaled to 0). *Screen:* terminal command, store errors, failing pods/events.
3. **Ticket opens.** Monitoring creates a bare Zammad ticket ("store 5xx rising"). *Screen:* Zammad shows a new ticket with almost no detail.
4. **Orchestrator collects.** It pulls logs, events, metrics and recent changes for the affected services. *Screen:* orchestrator console log listing each source it hit.
5. **Jev decides.** The orchestrator sends Jev the question with all the options and the evidence. Jev returns its choice: category = database outage, severity = P1, route = DB/platform team, action = restore Postgres. *Screen:* the request and response JSON, side by side (options in, decision out).
6. **Qwen writes.** Qwen on the DGX turns the evidence plus Jev's decision into a readable enrichment note. *Screen:* the note being generated.
7. **Ticket enriched.** The orchestrator posts the note to Zammad and sets priority, group and tags from Jev's decision. *Screen:* the same Zammad ticket, now complete and routed.
8. **Human closes the loop.** On-call approves the suggested action, the fix runs (Postgres scaled back), and the store recovers. *Screen:* approval in the ticket, then the store going green.

**Talking point:** the decision comes from a cheap, typed, auditable model call. The models only write; they don't act on their own. The harness controls what runs, and a human approves any change.

## Run order (operator)
Bring up app plus traffic, then Zammad, then orchestrator (Jev key and Qwen address from `.env`). Then: baseline, inject, watch, approve, recover. Reset by re-running the fault script with `--restore`.

The enrichment run is `python3 orchestrator/enrich.py --open`. It plays the incident response agent: it reads the ticket, asks Jev which diagnostic agents to call, calls them on Tanzu, checks their findings, asks Jev for the route, has Qwen write the prose, and posts one note. `docs/RUNBOOK.md` has the full rehearsal.

## Stage beats (INS-277)
1. **Storage latency.** A disk-heavy pod on a store worker VM writes to the vSAN datastore every store VM shares. One command starts it, one stops it (`fault-injection/storage_load.py`). The VCF agent reads the VMs' disk latency from VCF Operations. The access is applied. The load has not been run.
2. **Reasoning on screen.** The response agent's record (what it saw, the topology it loaded, the agents it called and why, every Jev option with its probability) is live on the Grafana board "Can I demo right now?".
3. **Topology.** The agent loads a static map in the order store, pods, VMs, datastore (`topology/metal-music.json`).
4. **PII.** The agent drafts a ticket holding a fake name, email, and 4111 card. pii-scrub replaces them before the text is stored, and the stored ticket shows the placeholders (`orchestrator/pii_ticket.py`).
5. **Denied action.** The VCF agent tries to stop a VM through AgentMinder and is refused with 403; the gateway's audit line names the same transaction (`orchestrator/deny_beat.py`). The audit line read waits on Security review INS-278.

**Talking point:** the audience sees why the agent chose, not only what it chose, and sees the guardrails refuse on cue.

## Diagnostic agents and skills
Each diagnostic agent runs on Tanzu with its own playbook skill, in a fixed order:

- **Load balancer (Avi):** virtual service, pool health, down members, errors.
- **Kubernetes:** deployments, pods (restarts, crash loops, out-of-memory kills), events, logs of the failing pods.
- **VCF, read-only:** host and VM health, datastore and resource pressure, alarms, disk latency of the store's VMs. No power operations.

Each agent answers with one findings JSON object (`skills/schema/findings.schema.json`). Every finding carries the tool it came from and the raw value. The harness rejects a finding that cites a tool the agent did not call.

The enrichment note has six sections: summary, likely root cause with confidence, evidence by domain, impact, next steps, and an access log of allowed and denied calls. The harness also sets the ticket priority, group, and tags.

**Talking point:** every claim in the note can be traced to one tool call that AgentMinder allowed, and the note says which calls were refused.

## Avi and AgentMinder
Avi is its own MCP door (`metal-avi-mcp` on Tanzu), not a plugin of the VCF MCP. It reads virtual service health, pool members, latency, 4xx/5xx, and service engine state.

Access control is AgentMinder. Each agent app in Cloud Foundry space `${GOAD_VCFA_SPACE}` has its own sidecar and its own bearer token, and reaches its doors through the AgentMinder AI Gateway. The load balancer agent reaches Avi that way and holds no Kubernetes or VCF grant. The grant table is `manifests/agentminder/grants.yaml`. The store ingress stays on nginx until an Avi ingress class exists.
