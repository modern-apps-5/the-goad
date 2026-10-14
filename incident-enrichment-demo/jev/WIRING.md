target: Goad org + Goad repo; nothing in Acme

# Jev gate wiring

The demo asks Jev from `orchestrator/jev.py`. `orchestrator/enrich.py` calls it twice: which diagnostic agents to run, then which helpdesk route to set. `orchestrator/orchestrator.py` can ask the same client one decision question.

Nothing in this package chooses an action from Jev's answer except the route and priority written onto the ticket. Jev does not receive a key from git.

Set these in a mode-600 env file that is not committed:

- `JEV_BASE_URL` — Jev root URL
- `JEV_API_KEY` — bearer key
- `JEV_MODEL` — defaults to `jev-1.13.0` inside `orchestrator/jev.py`

`orchestrator/jev.py` builds the decide path from the host of `JEV_BASE_URL`. Leave that host logic as it is. Fill the URL in the env file after the Captain approves PLAN.md.
