# Agents

What is mounted on the guest cluster today.

Each of the four agents runs `python:3.12-slim` with command
`python3 /app/idle.py`. The only file in that directory is `idle.py`,
from ConfigMap `agent-idle`. Env is `AGENT_NAME` and `PORT`. There is
no skill file, system prompt, report schema, or tool list in the pod
or in the image.

| Agent | Live command | Live files | Skill / prompt / tools |
|---|---|---|---|
| `incident-response-agent` | `python3 /app/idle.py` | `/app/idle.py` | none mounted |
| `lb-diagnostic-agent` | `python3 /app/idle.py` | `/app/idle.py` | none mounted |
| `k8s-diagnostic-agent` | `python3 /app/idle.py` | `/app/idle.py` | none mounted |
| `vcf-diagnostic-agent` | `python3 /app/idle.py` | `/app/idle.py` | none mounted |
| `pii-scrub` | `python3 /app/scrub.py` | `/app/scrub.py` from ConfigMap `pii-scrub` | none; `POST /scrub` redacts email and phone shapes |
| orchestrator | not deployed | `orchestrator/clm.py` is a library, not a pod | none mounted |

`idle.py` answers `/health` with `{"status":"idle"}`. It does not call
the model or the MCP servers. `demo/demo.sh start` does not start these
processes.
