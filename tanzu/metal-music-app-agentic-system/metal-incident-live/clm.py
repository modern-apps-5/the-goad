"""Ask CLM one routing question. CLM replaces Jev.

POST {CLM_BASE_URL}/v1/systemone with model clm-latest and no API key.
This module does not call Jev and does not choose an action.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def ask(caller: str, state: str, question: dict, *, timeout: float = 60) -> dict:
    root = os.environ.get("CLM_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("CLM_MODEL", "clm-latest")
    if not root:
        return {"decider": None, "error": "CLM_BASE_URL is unset", "response": None}
    payload = {"state": state, "model": model, "questions": {"q": question}}
    req = urllib.request.Request(
        root + "/v1/systemone",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "goad-agentic",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        return {"decider": None, "error": f"HTTP {exc.code} {detail}", "response": None, "caller": caller}
    except (OSError, json.JSONDecodeError) as exc:
        return {"decider": None, "error": type(exc).__name__, "response": None, "caller": caller}
    if not isinstance(body, dict):
        return {"decider": None, "error": "CLM response was not an object", "response": None, "caller": caller}
    return {"decider": "clm", "error": None, "response": body, "caller": caller}
