"""Call one Metal Music agent on Tanzu through its own chat API.

Agent Builder serves POST /api/chat as a Vercel AI data stream. The
stream carries every tool call and its result, so the harness sees which
tools the agent really used. Its A2A endpoint fails every task on
buildpack 0.0.53, so this is the door that works.

TLS trust for *.${TANZU_APPS_DOMAIN} comes from SSL_CERT_FILE (the
Ops Manager root bundle on agents-machine).
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
import uuid

DOMAIN = "${TANZU_APPS_DOMAIN}"
DOORS = ("k8s", "vcf", "avi")
DENIED_WORDS = ("denied", "forbidden", "not in this grant", "403", "unauthorized", "401")


def bare_tool(app: str, name: str) -> str:
    """`sc-k8s-diagnostic-agent-k8s_k8s_list_pods` becomes `k8s_list_pods`."""
    for door in DOORS:
        prefix = f"sc-{app}-{door}_"
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _context() -> ssl.SSLContext:
    bundle = os.environ.get("SSL_CERT_FILE") or os.path.expanduser("~/.config/tanzu-ca/ca-bundle.pem")
    return ssl.create_default_context(cafile=bundle if os.path.isfile(bundle) else None)


def ask(app: str, text: str, *, timeout: float = 600) -> dict:
    """One chat turn. Returns the reply text, every tool call, and run stats."""
    body = {
        "id": str(uuid.uuid4()),
        "trigger": "submit-message",
        "messages": [{"id": str(uuid.uuid4()), "role": "user", "parts": [{"type": "text", "text": text}]}],
    }
    req = urllib.request.Request(
        f"https://{app}.{DOMAIN}/api/chat",
        data=json.dumps(body).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    calls: dict[str, dict] = {}
    order: list[str] = []
    chunks: list[str] = []
    stats: dict = {}
    error = None
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_context()) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                kind = event.get("type")
                call_id = event.get("toolCallId")
                if kind == "tool-input-available" and call_id:
                    calls[call_id] = {"tool": bare_tool(app, event.get("toolName") or ""), "input": event.get("input")}
                    order.append(call_id)
                elif kind == "tool-output-available" and call_id in calls:
                    calls[call_id]["output"] = event.get("output")
                elif kind == "tool-output-error" and call_id in calls:
                    calls[call_id]["error"] = str(event.get("errorText") or "tool error")[:400]
                elif kind == "text-delta":
                    chunks.append(event.get("delta") or "")
                elif kind == "data-run-stats":
                    stats = event.get("data") or {}
                elif kind == "error":
                    error = str(event.get("errorText") or "agent error")[:400]
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}"
    except OSError as exc:
        error = type(exc).__name__
    rows = [calls[i] for i in order]
    for row in rows:
        out = row.get("output")
        text_out = json.dumps(out) if not isinstance(out, str) else out
        if "error" not in row and isinstance(out, (dict, str)) and _looks_denied(out):
            row["error"] = text_out[:400]
    return {
        "app": app,
        "text": "".join(chunks),
        "calls": rows,
        "stats": stats,
        "ms": int((time.perf_counter() - started) * 1000),
        "error": error,
    }


def _looks_denied(out: dict | str) -> bool:
    """A tool result that is itself a refusal, not data."""
    if isinstance(out, dict):
        if not (out.get("isError") or out.get("error")):
            return False
        return any(word in json.dumps(out).lower() for word in DENIED_WORDS)
    low = out.lower()
    return len(low) < 2000 and any(word in low for word in ("denied", "forbidden", "not in this grant"))


def _refused(reason: str) -> bool:
    low = reason.lower()
    return any(word in low for word in DENIED_WORDS)


def _unique(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


def allowed(result: dict) -> list[str]:
    """Tools that returned a result, each named once."""
    return _unique([c["tool"] for c in result["calls"] if "error" not in c and "output" in c])


def denied(result: dict) -> list[dict]:
    """Calls refused by AgentMinder, the door, or the system behind it."""
    seen: dict[str, dict] = {}
    for c in result["calls"]:
        if "error" in c and _refused(c["error"]):
            seen.setdefault(c["tool"], {"tool": c["tool"], "reason": c["error"]})
    return list(seen.values())


def failed(result: dict) -> list[dict]:
    """Calls that were allowed but broke, for example a door bug or a timeout."""
    seen: dict[str, dict] = {}
    for c in result["calls"]:
        if "error" in c and not _refused(c["error"]):
            seen.setdefault(c["tool"], {"tool": c["tool"], "reason": c["error"]})
    return list(seen.values())
