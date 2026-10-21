"""Call the local Kubernetes MCP. Does not shell out to kubectl.

Tokens come from the environment (see .env.example). They are never printed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from orchestrator.envfile import load_env

DEFAULT_URL = "http://127.0.0.1:8088/mcp"


def _token(write: bool) -> str:
    load_env()
    name = "MCP_WRITE_TOKEN" if write else "MCP_READ_TOKEN"
    token = os.environ.get(name) or ""
    if not token:
        raise RuntimeError(f"{name} is unset")
    return token


def call(tool: str, args: dict | None = None, *, write: bool = False, timeout: float = 30) -> dict:
    load_env()
    url = os.environ.get("K8S_MCP_URL") or DEFAULT_URL
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args or {}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {_token(write)}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"k8s MCP HTTP {exc.code}: {detail}") from exc
    except OSError as exc:
        raise RuntimeError(f"k8s MCP unreachable: {type(exc).__name__}") from exc
    if payload.get("error"):
        message = (payload.get("error") or {}).get("message") or "k8s MCP error"
        raise RuntimeError(str(message)[:400])
    content = ((payload.get("result") or {}).get("content") or [])
    text = content[0].get("text") if content else "{}"
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {"result": parsed}
