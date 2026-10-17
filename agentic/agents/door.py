"""One AgentMinder client calling one MCP door.

Mints a client-credentials token with resource set to the gateway URL,
then posts JSON-RPC to that gateway. Does not print the token.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def token() -> str:
    url = _env("AM_TOKEN_URL")
    client_id = _env("AM_CLIENT_ID")
    secret = _env("AM_CLIENT_SECRET")
    resource = _env("AM_GATEWAY")
    if not url or not client_id or not secret or not resource:
        raise RuntimeError("agent door env is incomplete")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "urn:iam:myscopes",
            "resource": resource,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic " + _basic(client_id, secret),
        },
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            doc = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"token HTTP {exc.code}") from exc
    access = doc.get("access_token") or ""
    if not access:
        raise RuntimeError("token response had no access_token")
    return access


def _basic(client_id: str, secret: str) -> str:
    import base64

    return base64.b64encode(f"{client_id}:{secret}".encode()).decode()


PROTOCOL = "2025-06-18"


def _post(url: str, access: str, payload: dict, session: str, timeout: float) -> tuple[dict, str]:
    headers = {
        "Authorization": f"Bearer {access}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL,
    }
    if session:
        headers["MCP-Session-Id"] = session
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=headers)
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        sid = resp.headers.get("MCP-Session-Id") or resp.headers.get("Mcp-Session-Id") or session
        raw = resp.read().decode()
    return json.loads(raw), sid or ""


def call_tool(name: str, arguments: dict, timeout: float = 40) -> dict:
    started = time.time()
    try:
        access = token()
        url = _env("AM_GATEWAY")
        opened, session = _post(
            url,
            access,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {},
                    "clientInfo": {"name": "goad-door", "version": "1"},
                },
            },
            "",
            timeout,
        )
        if isinstance(opened, dict) and opened.get("error"):
            err = opened["error"]
            message = err.get("message") if isinstance(err, dict) else str(err)
            return {
                "tool": name,
                "input": arguments,
                "ok": False,
                "error": str(message)[:300],
                "output": None,
                "ms": int((time.time() - started) * 1000),
            }
        doc, _session = _post(
            url,
            access,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            session,
            timeout,
        )
    except Exception as exc:
        return {
            "tool": name,
            "input": arguments,
            "ok": False,
            "error": type(exc).__name__ + (f" {exc}" if not str(exc).lower().count("bearer") else ""),
            "output": None,
            "ms": int((time.time() - started) * 1000),
        }
    ms = int((time.time() - started) * 1000)
    if isinstance(doc, dict) and doc.get("error"):
        err = doc["error"]
        message = err.get("message") if isinstance(err, dict) else str(err)
        return {"tool": name, "input": arguments, "ok": False, "error": str(message)[:300], "output": None, "ms": ms}
    result = doc.get("result") if isinstance(doc, dict) else doc
    # MCP tool result is often {content:[{text}], isError}
    output = result
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        texts = []
        for item in result["content"]:
            if isinstance(item, dict) and item.get("text"):
                texts.append(item["text"])
        if texts:
            joined = "\n".join(texts)
            try:
                output = json.loads(joined)
            except json.JSONDecodeError:
                output = {"text": joined[:4000]}
        if result.get("isError"):
            return {"tool": name, "input": arguments, "ok": False, "error": "tool isError", "output": output, "ms": ms}
    return {"tool": name, "input": arguments, "ok": True, "error": "", "output": output, "ms": ms}
