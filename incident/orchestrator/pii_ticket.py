#!/usr/bin/env python3
"""PII beat: the response agent files a ticket, and pii-scrub has cleaned it.

The operator's message carries a fake name, a fake email, and the test
card number 4111 1111 1111 1111. It goes to the incident response agent on
Tanzu. That agent's model sits behind the AI Services policy webhook
pii-scrub, which replaces personal data before the model reads it and
again on the reply. The agent drafts the ticket from what it saw, and
this script files exactly that draft in Zammad.

If any of the fake values survives in the draft, nothing is filed and
the script says pii-scrub did not scrub it.

    python3 orchestrator/pii_ticket.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator import tanzu_agents  # noqa: E402
from orchestrator.envfile import load_env  # noqa: E402
from orchestrator.findings import extract_json  # noqa: E402
from orchestrator.orchestrator import zammad_request  # noqa: E402

AGENT = "incident-response-agent"
ZAMMAD_UI = "http://${COMMAND_BOX_HOST}:8080/#ticket/zoom/"

FAKE_NAME = "John Smith"
FAKE_EMAIL = "john.smith@example.com"
FAKE_CARD = "4111 1111 1111 1111"
RAW_VALUES = (FAKE_NAME, FAKE_EMAIL, FAKE_CARD, FAKE_CARD.replace(" ", ""), "John", "Smith")
PLACEHOLDERS = ("<PERSON>", "<EMAIL_ADDRESS>", "<CREDIT_CARD>")

PROMPT = (
    "A shopper wrote to the help desk. This is not an incident run: do not run your skill and do not call any tool. "
    "Draft one Zammad ticket for the message below. Reply with one JSON object and nothing else: "
    '{"title": "...", "body": "..."}. In the body, copy the shopper\'s name, email address, and card number '
    "exactly as you see them in the message, so the help desk can follow up.\n\n"
    f"Shopper message: My name is {FAKE_NAME}. My email is {FAKE_EMAIL}. "
    f"Checkout failed on my card {FAKE_CARD} and the store showed an error page."
)


def draft() -> tuple[dict | None, dict]:
    result = tanzu_agents.ask(AGENT, PROMPT, timeout=900)
    doc = extract_json(result["text"]) if not result["error"] else None
    if not isinstance(doc, dict) or not doc.get("title") or not doc.get("body"):
        return None, result
    return {"title": str(doc["title"])[:200], "body": str(doc["body"])[:4000]}, result


def leaks(text: str) -> list[str]:
    return [value for value in RAW_VALUES if value.lower() in text.lower()]


def file_ticket(title: str, body: str) -> dict:
    status, raw = zammad_request(
        "POST",
        "/api/v1/tickets",
        {
            "title": title,
            "group": "Users",
            "customer_id": "guess:oncall@metal-store.lab",
            "article": {"subject": title, "body": body, "type": "note", "internal": False,
                        "content_type": "text/plain"},
        },
    )
    if status not in (200, 201):
        return {"status": status}
    ticket = json.loads(raw)
    zammad_request("POST", "/api/v1/tags/add", {"object": "Ticket", "o_id": ticket["id"], "item": "pii-beat"})
    return {"status": status, "id": ticket["id"], "number": ticket.get("number")}


def stored_body(ticket_id: int) -> str:
    status, raw = zammad_request("GET", f"/api/v1/ticket_articles/by_ticket/{ticket_id}", None)
    if status != 200:
        return ""
    return "\n".join(str(a.get("body") or "") for a in json.loads(raw) if isinstance(a, dict))


def main() -> int:
    load_env()
    print(f"Asking {AGENT} to draft a ticket from a message with a fake name, a fake email, and card 4111.")
    doc, result = draft()
    if doc is None:
        print(f"Not filed. The agent did not return a title and body ({result['error'] or 'no JSON in the reply'}).")
        return 1
    if result["calls"]:
        print(f"Note: the agent called {len(result['calls'])} tool(s) while drafting.")
    found = leaks(doc["title"] + "\n" + doc["body"])
    if found:
        print(f"Not filed. pii-scrub did not scrub the draft: {len(found)} fake value(s) came back unchanged.")
        return 1
    shown = [p for p in PLACEHOLDERS if p in doc["body"]]
    print(f"Draft from the agent ({result['ms']} ms). Placeholders in the body: {', '.join(shown) or 'none'}.")
    filed = file_ticket(doc["title"], doc["body"])
    if not filed.get("id"):
        print(f"Not filed. Zammad answered HTTP {filed['status']}.")
        return 1
    body = stored_body(filed["id"])
    stored_leaks = leaks(body)
    print(f"Filed Zammad ticket {filed['number']} (id {filed['id']}): {ZAMMAD_UI}{filed['id']}")
    print("Stored body:")
    print(body)
    if stored_leaks:
        print("The stored ticket still holds a fake value. The beat failed.")
        return 1
    print(f"The stored ticket holds none of the fake values. Placeholders stored: "
          f"{', '.join(p for p in PLACEHOLDERS if p in body) or 'none'}.")
    return 0 if all(p in body for p in PLACEHOLDERS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
