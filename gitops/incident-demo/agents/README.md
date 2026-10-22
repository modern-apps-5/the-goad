# Agents

The four agents, the orchestrator, and pii-scrub are Cloud Foundry
apps in org `Goad`, space `metal-music-app-agentic-system`. Push them
with `tanzu-agents/push.py`. The VKS pods of the same names were an earlier
placement and are not the runtime. `walk/demo.sh start` does not start
the agents. The Captain starts a walk by typing this in the incident
response chat on `https://incident-response-agent.${TANZU_APPS_DOMAIN}/`:

`pick up the latest incident ticket and enrich it`

| Piece | Command | Mounts | Calls |
|---|---|---|---|
| `incident-response-agent` | agent buildpack, `agents/roles/incident-response-agent.md` as `AGENTS.md` | the enrichment tools only. `chat.py` is not staged |
| `orchestrator` | `python3 /app/harness.py` | `agents/orchestrator/harness.py` | the three diagnostic agents, Qwen, Grafana. Decision gate is `CLM_URL` |
| `lb-diagnostic-agent` | agent buildpack, skill `lb_diagnostic_agent` | Avi door `avi_latency` |
| `k8s-diagnostic-agent` | agent buildpack, skill `k8s_diagnostic_agent` | `k8s_list_deployments`, `k8s_list_pods`, `k8s_events`, `k8s_pod_logs` |
| `vcf-diagnostic-agent` | agent buildpack, skill `vcf_diagnostic_agent` | `vcf_vm_disk_latency` |
| `pii-scrub` | `python3 /app/scrub.py` | `pii/scrub.py` | none |

`python3 tanzu-agents/push.py agents` stages `AGENTS.md` and the skill, clears
any `python chat.py` or `python diagnose.py` start command, and binds
the Goad qwen endpoint. The orchestrator exposes `enrich_latest_incident`
and `enrich_status` on `POST /mcp`. The guest deployments of the same
four names stay at 0 replicas. They are the old scripts.

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
