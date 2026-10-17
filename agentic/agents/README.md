# Agents

The four agents, the orchestrator, and pii-scrub are Cloud Foundry
apps in org `Goad`, space `metal-music-app-agentic-system`. Push them
with `tanzu/push.py`. The VKS pods of the same names were an earlier
placement and are not the runtime. `demo/demo.sh start` does not start
the agents. The Captain starts a walk by typing this in the incident
response chat on `https://incident-response-agent.${TANZU_APPS_DOMAIN}/`:

`pick up the latest incident ticket and enrich it`

| Piece | Command | Mounts | Calls |
|---|---|---|---|
| `incident-response-agent` | agent buildpack, `agents/roles/incident-response-agent.md` as `AGENTS.md` | the enrichment tools only. `chat.py` is not staged |
| `orchestrator` | `python3 /app/harness.py` | `orchestrator/harness.py` | the three diagnostic agents, Qwen, Grafana. Decision gate is `CLM_URL` |
| `lb-diagnostic-agent` | agent buildpack, skill `lb_diagnostic_agent` | Avi door `avi_latency` |
| `k8s-diagnostic-agent` | agent buildpack, skill `k8s_diagnostic_agent` | `k8s_list_deployments`, `k8s_list_pods`, `k8s_events`, `k8s_pod_logs` |
| `vcf-diagnostic-agent` | agent buildpack, skill `vcf_diagnostic_agent` | `vcf_vm_disk_latency` |
| `pii-scrub` | `python3 /app/scrub.py` | `pii/scrub.py` | none |

The apps that are already running still start `chat.py` and `diagnose.py`.
The next `tanzu/push.py` is what switches them to the buildpack above.
Do not push that until the orchestrator exposes `enrich_latest_incident`,
or the incident agent has no tool to call.

`CLM_URL` blank means the decision gate is on fallback. The note says
that. The orchestrator still calls all three agents. One stalled agent
does not stop the note. The VCF finding is the storage-latency cause
when write latency is hundreds of milliseconds.

The findings shape is `agents/schema/findings.schema.json`. The writer
skill at `agents/writer/skills/SKILL.md` is the prose shape the
orchestrator asks Qwen for. `agents/idle.py` is the earlier placeholder
and is not the live command.

Doors are the AgentMinder clients `py-goad-lb`, `py-goad-k8s`, and
`py-goad-vcf`. Secret key names are in `secrets/templates.yaml`.
