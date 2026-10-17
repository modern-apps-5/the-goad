# Agents

The four agents and the orchestrator run `python:3.12-slim` in
`metal-music-app-agentic-system`. `demo/demo.sh start` does not start
them. The Captain starts a walk by typing this in the incident
response chat:

`pick up the latest incident ticket and enrich it`

| Piece | Command | Mounts | Calls |
|---|---|---|---|
| `incident-response-agent` | `python3 /app/chat.py` | `agents/chat.py`, `agents/incident-response/skills/SKILL.md` | Zammad and the orchestrator only |
| `orchestrator` | `python3 /app/harness.py` | `orchestrator/harness.py` | the three diagnostic agents, Qwen, Grafana. Decision gate is `CLM_URL` |
| `lb-diagnostic-agent` | `python3 /app/diagnose.py` | `agents/diagnose.py`, `agents/door.py`, `agents/lb-diagnostic/skills/SKILL.md` | Avi door `avi_latency` |
| `k8s-diagnostic-agent` | `python3 /app/diagnose.py` | same code, `agents/k8s-diagnostic/skills/SKILL.md` | `k8s_list_deployments`, `k8s_list_pods`, `k8s_events`, `k8s_pod_logs` |
| `vcf-diagnostic-agent` | `python3 /app/diagnose.py` | same code, `agents/vcf-diagnostic/skills/SKILL.md` | `vcf_vm_disk_latency` |
| `pii-scrub` | `python3 /app/scrub.py` | `pii/scrub.py` | none |

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
