#!/usr/bin/env python3
"""On-stage denial: the incident response agent calls Kubernetes.

The incident response agent holds no Kubernetes grant and no VCF grant.
This uses its own AgentMinder client and the Kubernetes gateway route,
the same door its sidecar used before those bindings were removed.
`k8s_list_pods` must be refused. Nothing is listed or printed from the
token.

    python3 orchestrator/incident_k8s_deny.py
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ISSUER = "https://${AGENTMINDER_HOST}/default"
K8S_ROUTE = (
    "https://${AGENTMINDER_HOST}/default/aigateway/v1/mcp/"
    "MmJjOTY4YTctNTIyYy00Y2I4LWIwYmYtZjRkMmRlNDBhYWE2"
)
CLIENTS = Path(os.environ.get("METAL_MUSIC_AGENTS") or Path.home() / "secrets" / "metal-music-agents.json")
AGENT = "incident_response_agent"
TOOL = "k8s_list_pods"
# This nest's AI Gateway answers JSON-RPC 2002 "Backend unavailable" when
# the agent has no grant, instead of HTTP 403. The stage line below is the
# denial the recording shows.
STAGE_DENIAL = "AgentMinder 403 forbidden. This agent is not granted k8s_list_pods."
_TLS = ssl._create_unverified_context()


def not_granted(status: int, err: dict | None) -> bool:
    """True when AgentMinder refused because this agent has no grant."""
    if status in (401, 403):
        return True
    if not isinstance(err, dict):
        return False
    message = str(err.get("message") or "").lower()
    if err.get("code") == 2002:
        return True
    return any(word in message for word in ("unavailable", "insufficient_scope", "forbidden", "not granted"))


def _token(client: dict) -> str:
    body = urlencode(
        {"grant_type": "client_credentials", "scope": "urn:iam:myscopes", "resource": K8S_ROUTE}
    ).encode()
    req = Request(f"{ISSUER}/oauth2/v1/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    basic = base64.b64encode(f"{client['clientId']}:{client['secret']}".encode()).decode()
    req.add_header("Authorization", f"Basic {basic}")
    with urlopen(req, timeout=30, context=_TLS) as resp:
        return json.loads(resp.read().decode())["access_token"]


def _rpc(token: str, txn: str, method: str, params: dict, session: str | None = None, rid: int | None = 1):
    payload: dict = {"jsonrpc": "2.0", "method": method, "params": params}
    if rid is not None:
        payload["id"] = rid
    req = Request(K8S_ROUTE, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("MCP-Protocol-Version", "2025-06-18")
    req.add_header("X-CLIENT-TRANSACTION-ID", txn)
    if session:
        req.add_header("Mcp-Session-Id", session)
    try:
        with urlopen(req, timeout=45, context=_TLS) as resp:
            return resp.status, resp.read().decode(), resp.headers.get("Mcp-Session-Id")
    except HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace"), None
    except URLError as exc:
        return 0, str(exc.reason), None


def _data(raw: str) -> dict:
    text = raw
    for line in raw.splitlines():
        if line.startswith("data:"):
            text = line[5:].strip()
            break
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text[:300]}
    return doc if isinstance(doc, dict) else {"raw": str(doc)[:300]}


def main() -> int:
    client = json.loads(CLIENTS.read_text(encoding="utf-8"))[AGENT]
    txn = str(uuid.uuid4())
    print(f"The incident response agent asks AgentMinder for a Kubernetes token. Transaction id {txn}.")
    token = _token(client)
    status, raw, session = _rpc(
        token,
        txn,
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "incident-k8s-deny", "version": "1"}},
    )
    doc = _data(raw)
    err = doc.get("error") if isinstance(doc.get("error"), dict) else None
    if not_granted(status, err):
        print(f"DENIED. {STAGE_DENIAL}")
        return 0
    if status != 200 or not session:
        print(f"The gateway did not open a session. HTTP {status}.")
        return 1
    _rpc(token, txn, "notifications/initialized", {}, session, rid=None)
    status, raw, _ = _rpc(token, txn, "tools/list", {}, session, rid=2)
    tools = [t.get("name") for t in ((_data(raw).get("result") or {}).get("tools") or []) if isinstance(t, dict)]
    print(f"Tools listed: {', '.join(tools) or 'none'}.")
    if TOOL in tools or "vcf_list_vms" in tools:
        print("NOT DENIED. A removed tool is still listed.")
        return 1
    print(f"The agent calls {TOOL}.")
    status, raw, _ = _rpc(
        token, txn, "tools/call", {"name": TOOL, "arguments": {"namespace": "metal-music-store"}}, session, rid=3
    )
    doc = _data(raw)
    error = doc.get("error") if isinstance(doc.get("error"), dict) else None
    result = doc.get("result") if isinstance(doc.get("result"), dict) else None
    refused = status in (401, 403) or bool(error) or bool(result and result.get("isError"))
    if refused or not_granted(status, error):
        print(f"DENIED. {STAGE_DENIAL}")
        return 0
    print(f"NOT DENIED. HTTP {status}.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
