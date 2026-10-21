"""Call the three live doors. Tokens stay in the environment."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _file_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip("'").strip('"')
    return out


def load_local() -> None:
    for path in (
        Path.home() / "secrets" / "k8s-mcp.env",
        Path.home() / "secrets" / "avi-mcp.env",
        Path.home() / "secrets" / "vcf-mcp-http.env",
    ):
        for key, value in _file_env(path).items():
            os.environ.setdefault(key, value)


def jsonrpc(url: str, token: str, tool: str, args: dict, timeout: float = 60) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:240]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if payload.get("error"):
        raise RuntimeError(str((payload.get("error") or {}).get("message") or "mcp error")[:400])
    content = ((payload.get("result") or {}).get("content") or [])
    text = content[0].get("text") if content else "{}"
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _sse_json(raw: str) -> dict:
    for line in raw.splitlines():
        if line.startswith("data:"):
            text = line[5:].strip()
            if text:
                return json.loads(text)
    return json.loads(raw)


def streamable(url: str, token: str, tool: str, args: dict, timeout: float = 90) -> dict:
    """One Streamable HTTP session: initialize, then tools/call."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    def post(payload: dict, session: str | None) -> tuple[dict, str]:
        head = dict(headers)
        if session:
            head["Mcp-Session-Id"] = session
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers=head)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id") or session or ""
                raw = resp.read().decode()
                if not raw.strip():
                    return {}, sid
                return _sse_json(raw), sid
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:240]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    _, session = post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "incident-demo", "version": "1"},
            },
        },
        None,
    )
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    payload, _sid = post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        },
        session,
    )
    if payload.get("error"):
        raise RuntimeError(str((payload.get("error") or {}).get("message") or "vcf mcp error")[:400])
    content = ((payload.get("result") or {}).get("content") or [])
    if not content:
        return payload.get("result") if isinstance(payload.get("result"), dict) else {"result": payload.get("result")}
    text = content[0].get("text") if isinstance(content[0], dict) else ""
    if not text:
        return {"result": content}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text[:2000]}
    return parsed if isinstance(parsed, dict) else {"result": parsed}
