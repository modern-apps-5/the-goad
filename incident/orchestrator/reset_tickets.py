#!/usr/bin/env python3
"""Close open helpdesk tickets. Leave any ticket whose title says backup.

Then forget the last response agent run, here and on the live app, so the
Incident live board starts empty. The board keeps whichever copy is newer,
so both copies go.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.envfile import load_env  # noqa: E402
from orchestrator.orchestrator import zammad_request  # noqa: E402
from orchestrator.reasoning import PATH as REASONING_PATH  # noqa: E402

LIVE_URL = os.environ.get("INCIDENT_LIVE_URL") or "https://metal-incident-live.${TANZU_APPS_DOMAIN}/live"
LIVE_SECRETS = Path.home() / "secrets" / "metal-incident-live.env"


def _rows(status: int, body: str) -> list[dict] | None:
    if status != 200:
        return None
    try:
        doc = json.loads(body)
    except json.JSONDecodeError:
        return None
    return [row for row in doc if isinstance(row, dict)] if isinstance(doc, list) else None


def _open_tickets() -> list[dict] | None:
    """New and open tickets, read from the ticket list.

    The search index on this helpdesk answers a state query with an empty
    list, so search would close nothing.
    """
    states = _rows(*zammad_request("GET", "/api/v1/ticket_states", None))
    if states is None:
        return None
    open_ids = {row.get("id") for row in states if row.get("name") in ("new", "open")}
    tickets: list[dict] = []
    for page in range(1, 51):
        rows = _rows(*zammad_request("GET", f"/api/v1/tickets?per_page=100&page={page}", None))
        if rows is None:
            return None
        tickets.extend(rows)
        if len(rows) < 100:
            break
    return [row for row in tickets if row.get("state_id") in open_ids]


def _live_token() -> str:
    if not LIVE_SECRETS.is_file():
        return ""
    for line in LIVE_SECRETS.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip() == "MCP_TOKEN":
            return value.strip().strip('"').strip("'")
    return ""


def clear_live_board() -> str | None:
    """Return None when both copies of the last run are gone, else the reason they are not."""
    REASONING_PATH.unlink(missing_ok=True)
    token = _live_token()
    if not token:
        return f"no live app token in {LIVE_SECRETS}"
    bundle = os.environ.get("SSL_CERT_FILE") or os.path.expanduser("~/.config/tanzu-ca/ca-bundle.pem")
    ctx = ssl.create_default_context(cafile=bundle if os.path.isfile(bundle) else None)
    req = urllib.request.Request(
        LIVE_URL.rsplit("/", 1)[0] + "/reset",
        data=b"{}",
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        return "an enrichment is still running on the live app" if exc.code == 409 else f"live app reset HTTP {exc.code}"
    except OSError as exc:
        return f"live app reset {type(exc).__name__}"
    return None if code == 200 else f"live app reset HTTP {code}"


def main() -> int:
    load_env()
    rows = _open_tickets()
    if rows is None:
        print("could not list tickets")
        return 1
    closed = 0
    kept = 0
    for row in rows:
        title = str(row.get("title") or "")
        ticket_id = row.get("id")
        number = row.get("number")
        if not ticket_id:
            continue
        if "backup" in title.lower():
            kept += 1
            print(f"kept {number}: {title}")
            continue
        code, _ = zammad_request("PUT", f"/api/v1/tickets/{ticket_id}", {"state": "closed"})
        if code in (200, 201):
            closed += 1
            print(f"closed {number}")
        else:
            print(f"could not close {number}: HTTP {code}")
            return 1
    print(f"closed {closed}, kept {kept}")
    problem = clear_live_board()
    if problem:
        print(f"live board not cleared: {problem}")
        return 1
    print("live board cleared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
