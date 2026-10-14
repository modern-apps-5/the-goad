# Demo runbook

Run this on agents-machine, in the checkout of this repo. The store, Zammad, and Grafana were answering on 2026-10-11. AgentMinder is serving: a real agent sign-in returned 200 on 2026-10-12 at 11:49 UTC.

The three MCP doors run as Tanzu apps in space `${GOAD_VCFA_SPACE}` in org Goad: `metal-k8s-mcp`, `metal-vcf-mcp`, and `metal-avi-mcp`. Each answered `/health` 200 on 2026-10-12. The local MCP ports 8088, 8092, and 8093 on agents-machine were not listening on that day. Use the Tanzu doors. All four agents run. `docs/MAP.md` has the state of each app. agents-machine does not trust the Ops Manager root CA that signs `*.${TANZU_APPS_DOMAIN}` yet, so the checks below use `-k`.

Copy `orchestrator/.env.example` to `.env` in the repo root and fill it on this machine. Do not commit that file.

## 1. Open the healthy store

Open https://${STORE_HOST}/

On screen: the store page.

Verify:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://${STORE_HOST}/
```

Expect `200`.

## 2. Open the boards

Open these. Each returned HTTP 200 on the last check.

- DGX spark1: http://${SPARK_HOST}:3000/d/dgx-spark1/dgx-spark1
- Company efficiency: http://${SPARK_HOST}:3000/d/company-efficiency/company-efficiency

On screen: the board titled "DGX spark1", then the board titled "Company efficiency". The same two boards are on lab-observer if you are not on the spark1 network:

- https://${OBSERVER_HOST}:3000/d/dgx-spark1/dgx-spark1
- https://${OBSERVER_HOST}:3000/d/company-efficiency/company-efficiency

Verify: the page title matches the board, and the panels are not an error banner.

Then open the reasoning board: https://${OBSERVER_HOST}:3000/d/captain-demo-ready/can-i-demo-right-now

On screen: the board "Can I demo right now?". At the bottom is the row "Incident response agent: what it saw, what it loaded, whom it called, what Jev decided". Before the first run its Run panel says `none yet`. Keep this tab open; it refreshes while the agent works.

## 3. Confirm the doors

```bash
for d in metal-k8s-mcp metal-vcf-mcp metal-avi-mcp; do
  curl -sk -o /dev/null -w "$d %{http_code}\n" https://$d.${TANZU_APPS_DOMAIN}/health
done
```

Expect `200` for each. `-k` is there because this box does not trust the Ops Manager root CA yet. To push or re-push a door: `python3 manifests/tanzu/push.py mcp k8s` (or `vcf`, `avi`). Staging on this foundation took more than ten minutes per app on 2026-10-11. A push of one agent took between three and twelve minutes on 2026-10-12. Run one push at a time per app. Two pushes of the same app collide with `Only one build can be STAGING at a time per application`. Run the push in the foreground of a terminal that stays open. A push started with `nohup ... &` from a short-lived shell was killed after the manifest step on 2026-10-12.

If you change a door's environment, restart that app so the process reads it. `metal-vcf-mcp` kept verifying TLS until it was restarted after `VCF_MCP_OAUTH_TLS_VERIFY=0` was set. `cf restart` can time out on this cell while the instance still comes up. Check `cf app <name>` before you restart again.

## 4. Open the existing ticket

Open http://${COMMAND_BOX_HOST}:8080/

Sign in with the helpdesk user from the local env file.

Open http://${COMMAND_BOX_HOST}:8080/#ticket/zoom/3

On screen: ticket number 34003, title `store 5xx rising`.

Verify, with the helpdesk token in the environment and not on the command line:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Token token=$ZAMMAD_TOKEN" \
  http://${COMMAND_BOX_HOST}:8080/api/v1/tickets/3
```

Expect `200`. `GET /api/v1/tickets/34003` is 404. The number and the API id are different.

## 5. Slow the store and open the ticket

```bash
./demo.sh start
```

This slows catalog and checkout queries by 10 seconds and opens the incident ticket. The store stays up. It does not call the agents and it does not copy the ticket to them.

On screen: `Database latency applied: catalog queries sleep 10 seconds.`, `store HTTP 200 in <ms> ms` with ms at least 8000, and `opened ticket <number>: Metal Music Store slow: checkout and catalog pages taking 10+ seconds`. Then: `The incident response agent can pick this ticket up in chat.` and `Enrichment was not started.`

Reload the store page. Expect the shop, slowly. Expect HTTP 200.

## 6. Enrich from the incident response agent chat

Open https://incident-response-agent.${TANZU_APPS_DOMAIN}/ and type:

```text
pick up the latest incident ticket and enrich it
```

On screen, in that chat: the ticket, the assessment, Jev's probabilities and the 0.70 rule, which domain agents were called and what they found, and the enrichment text. The live board fills in while this runs:

https://${OBSERVER_HOST}:3000/d/captain-incident-live

Backup, from this machine, if you are not using the chat:

```bash
./demo.sh enrich
```

The older four-call walk is still available as `python3 orchestrator/orchestrator.py`. The presenter path is the chat above.

```bash
python3 orchestrator/orchestrator.py
```

On screen, before the model calls:

```text
skill incident_response_agent version 2026-10-11.1 loaded
skill k8s_diagnostic_agent version 2026-10-11.1 loaded
```

The writer prints the same kind of line. The four Qwen calls are one at a time. The demo door is the `X-Llamagate-Class: demo` header.

Then a JSON object. Expect:

- `serial_ok` true
- `jev` with a choice
- `qwen_ms` with four timings and model `qwen3.5:122b-a10b`
- `ticket` with the new Zammad id
- `posted` without the article body

Verify: open `http://${COMMAND_BOX_HOST}:8080/#ticket/zoom/<id>` using the id from that JSON. On screen: a second note on the ticket, plus the priority and group the harness set.

The default Qwen door can answer `gpu_busy` while a demo lock is on. This run uses the demo class. If the JSON says `serial_ok` false, read the last error in the terminal and do not start a second overlapping run.

### 6b. Show the reasoning

While the chat enrichment runs, switch to the live board. It refreshes every 5 seconds.

On screen, filled in as the agent works:

- **Run**: the ticket number, `running`, then `done` or `failed`.
- **What it saw**: the ticket text and the store's HTTP status.
- **Topology it loaded**: store, then pods, then VMs, then the datastore, from `topology/metal-music.json`.
- **Jev decisions with probabilities**: one row per option for "which agents" and for "which route", each with its probability on a bar. Jev's pick also shows Jev's confidence in it, a separate number. The agent follows the pick only when that confidence is 0.70 or more; otherwise it checks every domain, or routes to On-call. A row marked `used` is the choice the agent acted on.
- **Agents it called and why**: each diagnostic agent, the reason, its status, and how many findings it returned.
- **Steps, newest first**.

Verify: `curl -s http://${COMMAND_BOX_HOST}:8765/api/incident/reasoning` shows the same ticket number.

## 7. AgentMinder allow and deny

An empty token POST is not a health check. On 2026-10-12 it answered 500 while real sign-ins answered 200. `push.py agents` signs in with an agent's own client and prints `AgentMinder client sign-in HTTP 200` when the issuer is up.

`python3 manifests/tanzu/push.py agents` (or `agents <name>`) uploads, binds, and stages the agents in space `${GOAD_VCFA_SPACE}`. Each gets its own sidecar token, its own `sc-<agent>-<door>` MCP service pointing at its sidecar on `127.0.0.1:8181`, and the `spark1-llm` model. It starts an agent only when the sign-in is 200, the agent has a client, and every door has a gateway route. Otherwise it prints why the agent stayed stopped.

Already in place on 2026-10-12:

1. The four AgentMinder clients and grants, from `python3 departments/it/mcp/metal_music_grants.py` in the company brain. It writes `~/secrets/metal-music-agents.json`.
2. AI Gateway routes for `metal-k8s-mcp` and `metal-vcf-mcp`, set on each door app as `IDSP_GATEWAY_RESOURCE`. Avi is not an AgentMinder resource server and has no route.
3. The sidecar bridge asks for scope `urn:iam:myscopes`, so the agent's token carries its granted tool names. Every bind shows the gateway's own grant-filtered list. An agent holds no direct door token.
4. The five read-only VCF tools are bound to per-tool intents, so a grant names one tool. No agent has a power operation.
5. The load balancer agent's sidecar is bound to the Kubernetes route, the same pattern as the K8s agent, with no grant. Avi is not an AgentMinder resource server, so it has no gateway route.
6. `pii-scrub` in the Goad space has a 60 second health-check timeout. Every agent's model call goes through it.

The demo, on 2026-10-12 between 11:44 and 12:00 UTC. All four agents run in `cf apps`. Open each Debug view at `https://<agent>.${TANZU_APPS_DOMAIN}/` and ask it to list its tools and call one.

7. Allow. `k8s-diagnostic-agent` lists `k8s_list_namespaces`, `k8s_list_pods`, `k8s_list_deployments`. Asked for `k8s_list_pods` on `kube-system`, it answered 17 pods, first `antrea-agent-9dw58`, phase Running.
8. Allow, that morning. `vcf-diagnostic-agent` lists exactly `vcf_list_vms`, `vcf_get_vm`, `vcf_list_datastores`, `vcf_get_datastore`, `vcf_list_alerts`. `vcf_list_vms` answered 44 VMs. `incident-response-agent` listed `k8s_list_pods` and `vcf_list_vms` that morning, and both calls answered. Those two grants were removed the same day at 16:20 ET. See 9b.
9. Deny. `lb-diagnostic-agent` shows its Kubernetes bind connected with 0 tools. Asked to call `k8s_list_pods` on `kube-system`, it answered that the tool is not available to it. Through the gateway with its own client, initialize answers JSON-RPC 2002, `AI Gateway: Backend unavailable`, so no session opens and no tool runs. This deny is a Kubernetes call, not an Avi call.
9b. Deny, on stage. `incident-response-agent` has no Kubernetes or VCF grant and no `sc-incident-response-agent-k8s` or `sc-incident-response-agent-vcf` binding. Open its Debug view and the MCP Servers panel: it says "No MCP servers connected." Then:

```bash
python3 orchestrator/incident_k8s_deny.py
```

On screen the script prints `AgentMinder 403 forbidden. This agent is not granted k8s_list_pods.` This gateway still answers JSON-RPC 2002 when the agent has no grant. The stage line is that refusal, not the words "Backend unavailable". The Kubernetes diagnostic agent still lists `k8s_list_pods` on that same route, so the door is serving and this agent is the one refused.
10. Deny, that morning. Through the gateway with each agent's own client, `vcf_stop_vm` for the VCF agent and `vcf_get_vm` for the incident agent answered 403. The gateway never forwarded the call. The incident agent's current Kubernetes denial is 9b: the gateway will not open a session.
11. The company AgentMinder admin door has no audit tool, so the gateway's audit rows were not re-read from agents-machine. Earlier rows of an allow and a deny were recorded on 2026-10-12 at 03:08 UTC.

### 7b. The denied action, on stage

```bash
python3 orchestrator/deny_beat.py
```

On screen: the VCF agent's tool list (six read-only tools, no power operation), then `The agent calls vcf_stop_vm on vm-does-not-exist. Transaction id <uuid>.`, then `DENIED. HTTP 403.`, then a line saying the gateway's audit line for that transaction is read by hand.

Verify: the 403 and the transaction id. Rehearsed on 2026-10-12 at 19:03:57 UTC: HTTP 403, transaction `1e7cc7b0-984d-4203-964e-44dc109c9b57`. Security (INS-284) keeps the gateway log read off stage: IT or Number One reads it afterwards with `--read-audit`, until IT confirms the log carries no bearer tokens. On stage, say the gateway refused and show the 403.

## 8. Restore

```bash
./demo.sh restore
```

On screen: `Database latency removed.` and `store restored: HTTP 200`. The page is fast again. The command does not create a database pod.

Verify:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://${STORE_HOST}/
```

Expect `200`. Reload the store page and expect the shop again, without the long wait.

## 9. Storage latency

Security approved this on INS-278 and the Captain's 11:50 decision applied it. The Role is on the fault account, and the VCF agent is granted `vcf_vm_disk_latency`. The load has not been run. Do not run `start` while guest etcd or vSAN writes are still failing. If the door refuses, `start` prints `Not started. The Kubernetes door refused`.

```bash
python3 fault-injection/storage_load.py start
```

On screen: `Started storage-load on ...-xlw4k.` The pod writes 1 GiB files with direct I/O to the vSAN datastore the store's VMs share. Wait at least 5 minutes; VCF Operations collects every 5 minutes.

Run the enrichment (`python3 orchestrator/enrich.py --open --title "store slow"`). The VCF agent calls `vcf_vm_disk_latency` for the store's three worker VMs. Expect a finding of 20 ms or more on those VMs, against a baseline of 4.7 to 10.7 ms on 2026-10-12.

Stop it:

```bash
python3 fault-injection/storage_load.py stop
```

Verify: `python3 fault-injection/storage_load.py status` prints `storage-load is not running`. The pod also stops itself after 15 minutes.

## 10. PII is scrubbed before it is stored

```bash
python3 orchestrator/pii_ticket.py
```

On screen: the incident response agent drafts a ticket from a message with a fake customer (John Smith, john.smith@example.com, card 4111 1111 1111 1111). The script prints the new Zammad ticket link and the stored body. Expect `<PERSON>`, `<EMAIL_ADDRESS>`, and `<CREDIT_CARD>` where the values were.

Verify: open the printed link. The stored ticket shows the placeholders, not the values. The script exits 0 only when all three placeholders are stored.

Paperclip INS-256 waited on the four agents running and listing their tools: http://${COMMAND_BOX_HOST}:3100/issues/INS-256
