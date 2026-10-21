# Runbook — Metal Music incident agents

## MCP doors
The three doors run on Tanzu in space `${GOAD_VCFA_SPACE}`: `https://metal-k8s-mcp.${TANZU_APPS_DOMAIN}/mcp`, `https://metal-vcf-mcp.${TANZU_APPS_DOMAIN}/mcp`, and `https://metal-avi-mcp.${TANZU_APPS_DOMAIN}/mcp`. `GET /health` on each must be 200 before a demo. Push or re-push with `python3 manifests/tanzu/push.py mcp k8s` (or `vcf`, `avi`). The local ports 8088, 8092, and 8093 on agents-machine are not used by this demo.

`metal-avi-mcp` reads `AVI_CONTROLLER` and the NSX ALB password from app env set by `push.py`, never from this repo. Its controller session expires. `avi-mcp/client.py` signs in again once when the controller answers 401, so a long-running door does not need a restart. VCF alarms need the `ops` host in the vcf-mcp hosts file. After a `cf set-env` on a door, restart that app so the process reads the new value. Do not put passwords in this repo.

The nested Avi controller is slow: a sign-in took 25 seconds, and a whole-estate health view (one runtime call per virtual service or pool) took 29 to 51 seconds. The AI Gateway drops a backend call after 30 seconds and sends the caller nothing, so the agent's sidecar then waits its own 300 seconds. So `avi_vs_health` and `avi_pool_member_health` without a name answer from a snapshot that a background thread refreshes every 60 seconds (`AVI_SNAPSHOT_SECONDS`), stamped `as_of`. That refresh also keeps the controller session alive. A call that names one object is live. Controller calls share one session behind a lock.

The model path's PII filter rewrites parts of some Avi names before the model sees them. `ca806d9f-e62--kube-system-mgmt-image-proxy` reaches the model as `ca806d9f-<US_DRIVER_LICENSE>--kube-system-mgmt-image-proxy`, and the model sends that back. The door treats such a placeholder as a wildcard. A name that matches nothing returns `matched: false` and the valid names, not an error, because Agent Builder allows one retry per tool before it fails the whole turn.

`metal-avi-mcp` accepts two kinds of bearer: its own static read and write tokens, and an AgentMinder gateway token whose audience is its gateway route (`IDSP_GATEWAY_RESOURCE`, set by `push.py`). `push.py` stages `idsp_bearer.py` from the company brain beside the door. A gateway token is read-only, and when the token names tools, `tools/list` and `tools/call` keep to those tools.

## AgentMinder
Each Cloud Foundry app in space `${GOAD_VCFA_SPACE}` (display name Metal Music App Agentic System) runs the Tanzu Agent Builder (`agent_buildpack`). A diagnostic agent also runs the official AgentMinder sidecar on 127.0.0.1:8181. The sidecar mints a bearer token from that app's own client id and secret (`cf set-env`, never the manifest). It will not start unless `AGENTMINDER_SIDECAR_RESOURCE_0_URL` is set, so the incident response agent, which has no Kubernetes or VCF door, does not run it. Grants are applied with `departments/it/mcp/metal_music_grants.py` in the company brain. The public table is `manifests/agentminder/grants.yaml`. The incident response agent's grant map is empty.

`metal_music_grants.py` is safe to re-run. In order it:

1. creates the `avi-mcp` resource server if it is missing, in Sidecar mode with the gateway route as primary audience and the door as secondary audience, with access tokens required and policies enforced;
2. binds every granted tool to its own intent (`urn:iam:agent:intent:<tool>`);
3. adds that intent to any role that held the tool through an old group intent, so a rebind does not take a tool away;
4. creates or updates one role per agent and door, and grants it to the agent.

Do not grant `vm-management`; it carries power operations. A binding change takes about two minutes to reach the gateway's call check. The AgentMinder admin door cuts replies at 80,000 characters, so the script reads each resource server by name instead of listing them all.

The sidecar bridge asks AgentMinder for scope `urn:iam:myscopes`, so the token carries the agent's granted tool names. Without it the gateway answers 2002. Every agent reaches Qwen through `spark1-llm`, which goes through `pii-scrub` in the Goad space. Keep its health-check timeout at 60 seconds: `cf curl /v3/processes/<guid> -X PATCH -d '{"health_check":{"data":{"invocation_timeout":60}}}'`, then restart it. Push with `CF_STARTUP_TIMEOUT=20 python3 manifests/tanzu/push.py agents <name>`. On this one slow cell an agent takes 5 to 13 minutes to start, and the `cf` client's default 5 minute wait stops the script before the next agent. The platform API can also answer 500 for a few minutes when its database connection drops. If a restart fails that way, check that the app's current droplet is the new one (`cf curl /v3/apps/<guid>/droplets/current`), `cf set-droplet` it if not, and start the app again. It starts an agent only after a real client sign-in returns 200. An empty token POST answers 500 on a healthy issuer. Copy `agentminder` from the official SDK image into `agents/sidecar/site-packages/` before push. That directory is gitignored.

## Skills and findings
Each agent's playbook is `skills/<agent>/SKILL.md`. `push.py agents` stages it as `.agents/skills/<agent>/SKILL.md` with `skills/schema/findings.schema.json` beside it, which is where Agent Builder looks for skills. The agent's role file (`agents/roles/<app>.md`, staged as `AGENTS.md`) tells it to run that skill and reply with findings JSON.

Agent Builder's output is plain text; it has no output schema. The caller validates. `orchestrator/findings.py` holds Pydantic models that match `findings.schema.json` field for field, and `tests/test_findings.py` checks they stay in step: `python3 -m unittest discover -s tests`. A report is rejected when it fails the schema, names the wrong agent, or cites an `evidence.tool` or `tools_used` entry the agent did not actually call in that turn.

## Calling an agent
Use the chat API: `POST https://<agent>.${TANZU_APPS_DOMAIN}/api/chat`. It streams Server-Sent Events, and every tool call appears as `tool-input-available` then `tool-output-available`. `orchestrator/tanzu_agents.py` is the client. The A2A endpoint (`/a2a`, `message/send`) fails every task in about 0.1 seconds with no log on buildpack 0.0.53, so the harness does not use it. Tool names in the stream carry the bind name, for example `sc-k8s-diagnostic-agent-k8s_k8s_list_pods`; `tanzu_agents.bare_tool` strips that prefix.

## Enrichment run
`python3 orchestrator/enrich.py --open` opens a bare ticket, as monitoring would, then enriches it. `--ticket <id>` enriches an existing ticket by Zammad id (not the ticket number). It needs `.env` with the Jev, Qwen, and Zammad entries. The run report is `orchestrator/last-enrichment.json` (gitignored). The four route groups (`Database and platform`, `Load balancer`, `Store application`, `On-call`) are created on first use, and the on-call user is given access so the moved ticket stays visible.

Presenter path: `./demo.sh start` slows catalog queries by 10 seconds and opens the ticket `Metal Music Store slow: checkout and catalog pages taking 10+ seconds`. It does not scale Postgres, it does not call the agents, and it does not copy the ticket. Enrichment starts in the incident response agent chat with `pick up the latest incident ticket and enrich it`. The agent asks for the latest open ticket. The company watch reads it, because the Tanzu cell cannot reach the helpdesk. `./demo.sh enrich` is the backup. `./demo.sh restore` removes the delay, waits until the store answers HTTP 200 quickly, and prints `store restored: HTTP 200`.

Limits found on 2026-10-12:

- The database fault can be injected by the fault script, not by the Kubernetes diagnostic agent. The agent's account `k8s-diag` is read-only: get, list, and watch on pods, events, and deployments, and get on pod logs. Scale and pod delete sit on a separate account, `k8s-mcp-fault`, limited to `metal-music-store`, because the outage demo needs them. Creating a pod is still refused. `./demo.sh restore` scales the deployment back to 1 and waits until the store answers HTTP 200. It does not create a pod. A run on 2026-10-12 scaled postgres to 0, the store returned HTTP 500, and scaling back to 1 returned HTTP 200.
- Agent Builder fails a whole chat turn when the same tool errors twice. The prompt and the skills tell each agent never to call a refused tool again. The harness gives each agent three tries.
- A model call longer than about 60 seconds is cut somewhere in the AI Services path (`peer closed connection without sending complete message body`). Long tool results and a long JSON reply hit it. The skills keep replies to at most 6 findings with short `raw_value` quotes, and the VCF agent asks for a small inventory.
- `vcf_list_alerts` used to return an empty reply through the AI Gateway, and the agent broke on it. VCF Operations keeps every cancelled alert (15 253 that day), so the plain alert list made a 116 KB reply. Fixed on 2026-10-12 in vcf-mcp `cf1e39d`: the tool asks Operations for active alerts only and returns `count`, `by_level`, and the top 25 rows, critical first, with alert and resource names. Through the gateway with the VCF agent's own client it answered 40 active alerts in 11.5 KB.
- `push.py mcp vcf` sets the door's health-check timeout to 60 seconds. A push before that fix reset it to 10 seconds, which a slow cell can trip.
- When Jev's choice of agents is below 0.70, the harness checks all three domains and says so in the note. When Jev's route is below 0.70, the ticket goes to On-call at normal priority, and the note says so.
- With thinking on, Qwen spent all 1500 output tokens thinking and returned no answer, so the prose sections came back empty. The narrative call sends `reasoning_effort: none`, which this endpoint honours. `enable_thinking` and `think` are ignored.
## Topology and the reasoning record
`orchestrator/topology.py` loads `topology/metal-music.json` (store, pods, VMs, datastore) and refuses a file whose order is wrong or whose pods name a VM, or VMs a datastore, that the file does not list. `tests/test_topology.py` checks that. `enrich.py` loads it at the start of every run, puts it in the state Jev sees, and passes the store's worker VM names to the VCF agent.

`orchestrator/reasoning.py` writes `orchestrator/last-reasoning.json` (gitignored) at every step: what the agent saw, the topology it loaded, each Jev decision with every option's probability, each agent it called with the reason and the result, and the steps. It writes a temporary file and renames it, so a reader never sees half a record. The company brain's `ops/serve.py` serves it at `/api/incident/reasoning`, and the Grafana board "Can I demo right now?" on lab-observer shows it. Set `REASONING_PATH` to move the record; then set `INCIDENT_REASONING_PATH` to the same path for the watch.

## Storage latency fault
`python3 fault-injection/storage_load.py start` creates pod `storage-load` in `metal-music-store` on worker `...-xlw4k`. It writes 1 GiB files to an emptyDir with direct I/O in a loop. All of the store's VMs share the vSAN datastore `${VSAN_DATASTORE}`, so the writes land on the store's storage. `stop` deletes the pod, `status` prints its phase. The pod stops itself after 15 minutes, has a 2 GiB disk limit, and uses the store's own database image. It goes through the Kubernetes door only.

The VCF side reads latency with `vcf_vm_disk_latency` (vcf-mcp). VCF Operations collects every 5 minutes, so start the load at least 5 minutes before the VCF agent runs.

Applied on 2026-10-12 under Security's INS-278 conditions. The fault account may create the `storage-load` pod, and the door still refuses any other pod. Captain 2026-10-12 17:57 ET: do not run `start`. The demo replays the recorded disk-latency sample instead (`VCF_DISK_LATENCY_REPLAY=on` on `metal-vcf-mcp`). That does not change the lab. The gateway log read (item 2) is still not applied.

## PII beat
`python3 orchestrator/pii_ticket.py` asks the incident response agent on Tanzu to write a ticket that holds a made-up customer: John Smith, john.smith@example.com, card 4111 1111 1111 1111. The agent's model call goes through `pii-scrub`, so the text comes back with `<PERSON>`, `<EMAIL_ADDRESS>`, and `<CREDIT_CARD>` in place of the values. The script files that text in Zammad with tag `pii-beat`, reads the stored ticket back, and exits 0 only when all three placeholders are stored. If any raw value comes back from the agent, it refuses to file the ticket and exits 1. The values are fake; do not use a real person's details.

## Denied action
`python3 orchestrator/deny_beat.py` signs in as the VCF agent with its own client and calls `vcf_stop_vm` on a VM that does not exist, through the AgentMinder gateway. It prints `DENIED` with the HTTP status and a transaction id. It does not read the gateway log on its own. Security decided on INS-284 that the gateway's audit line is a manual read by IT or Number One, with no new access rule, until IT has checked that the gateway log carries no bearer tokens. `--read-audit` does that read through the Kubernetes door (account `k8s-diag`, which can read pod logs cluster-wide), prints only the lines with the transaction id, and masks bearer tokens and JWTs. Do not run `--read-audit` on stage. The VM name is fake on purpose: if a deny ever failed, nothing would stop.

## Ingress
The store ingress stays on the nginx class until the guest cluster has an Avi ingress class. Do not point it at Avi before that class exists.
