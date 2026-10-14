"""Ask Jev one routing question. No key is printed or stored."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from orchestrator.envfile import load_env


def decide_url(root: str) -> str:
    base = root.strip().rstrip("/")
    host = base.split("://", 1)[-1].split("/", 1)[0].split("@")[-1].lower()
    if host == "api.typesafe.ai":
        return base + "/v1/systemone"
    if host == "jevtypesafeai.com" or host.endswith(".jevtypesafeai.com"):
        if base.endswith("/api"):
            return base + "/v1/decide"
        return base + "/api/v1/decide"
    return base + "/v1/decide"


def ask(caller: str, state: str, question: dict, *, timeout: float = 60) -> dict:
    """POST one question. Returns decider, error, and the response body.

    Does not choose an action. On error, response is null.
    """
    load_env()
    api_key = os.environ.get("JEV_API_KEY", "")
    root = os.environ.get("JEV_BASE_URL", "").rstrip("/")
    model = os.environ.get("JEV_MODEL", "jev-1.13.0")
    if not api_key or not root:
        return {"decider": None, "error": "JEV_BASE_URL or JEV_API_KEY is unset", "response": None}
    payload = {"state": state, "model": model, "questions": {"q": question}}
    req = urllib.request.Request(
        decide_url(root),
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "incident-enrichment-demo",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300].replace(api_key, "[redacted]")
        return {"decider": None, "error": f"HTTP {exc.code} {detail}", "response": None}
    except (OSError, json.JSONDecodeError) as exc:
        return {"decider": None, "error": type(exc).__name__, "response": None}
    if not isinstance(body, dict):
        return {"decider": None, "error": "Jev response was not an object", "response": None}
    return {"decider": body.get("decider") or "jev", "error": None, "response": body, "caller": caller}
