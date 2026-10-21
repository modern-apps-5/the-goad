#!/usr/bin/env python3
"""Slow the store and open the incident ticket.

Does not call the agents and does not copy the ticket to them. The
Captain starts enrichment in the incident response agent's chat. The
agent reads the latest open ticket itself.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_fault_path = ROOT / "fault-injection" / "fault.py"
_spec = importlib.util.spec_from_file_location("metal_fault", _fault_path)
fault = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fault)

from orchestrator.envfile import load_env  # noqa: E402
from orchestrator.incident_title import TITLE  # noqa: E402
from orchestrator.orchestrator import open_ticket, store_status, zammad_request  # noqa: E402

def main() -> int:
    load_env()
    if fault.inject() != 0:
        return 1
    store = store_status()
    if store.get("status") == 200 and isinstance(store.get("ms"), int) and store["ms"] < 8000:
        store = store_status()
    print(f"store HTTP {store.get('status')} in {store.get('ms')} ms")
    if store.get("status") != 200:
        print("The store is not HTTP 200, so no incident ticket was opened.")
        return 1
    if not isinstance(store.get("ms"), int) or store["ms"] < 8000:
        print("The pages are not slow yet, so no incident ticket was opened.")
        return 1
    opened = open_ticket(store, TITLE)
    ticket_id = opened.get("ticket_id")
    if not ticket_id:
        print(f"could not open a ticket: HTTP {opened.get('status')}")
        return 1
    status, body = zammad_request("GET", f"/api/v1/tickets/{ticket_id}", None)
    number = ""
    title = TITLE
    if status == 200:
        try:
            doc = json.loads(body)
            number = str(doc.get("number") or "")
            title = doc.get("title") or TITLE
        except json.JSONDecodeError:
            number = ""
    print(f"opened ticket {number or ticket_id}: {title}")
    print("The incident response agent can pick this ticket up in chat.")
    print("Enrichment was not started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
