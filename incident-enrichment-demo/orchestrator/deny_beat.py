#!/usr/bin/env python3
"""Denied action beat: the VCF diagnostic agent tries to power off a VM.

The call uses the VCF agent's own AgentMinder client and goes through the
AI Gateway, exactly as its sidecar would. The agent holds read-only VCF
grants, so the gateway refuses `vcf_stop_vm` and never forwards it. The
VM id does not exist, so even a broken gate could not stop anything.

The gateway's audit line for the refusal is read by hand, not on stage.
Security (INS-284) allows no automatic read of the gateway log until IT
has checked that it carries no bearer tokens. IT or Number One may run
the read on demand; token-like strings are masked before printing.

    python3 orchestrator/deny_beat.py
    python3 orchestrator/deny_beat.py --read-audit   # IT or Number One only

No token, key, or password is printed.
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.k8s import call as k8s_call  # noqa: E402

ISSUER = "https://${AGENTMINDER_HOST}/default"
VCF_ROUTE = "${AGENTMINDER_GATEWAY_VCF}"
CLIENTS = Path(os.environ.get("METAL_MUSIC_AGENTS") or Path.home() / "secrets" / "metal-music-agents.json")
AGENT = "vcf_diagnostic_agent"
TOOL = "vcf_stop_vm"
TARGET_VM = "vm-does-not-exist"
# The issuer and gateway routes are signed by the lab CA, which this machine
# does not trust yet (INS-260).
_TLS = ssl._create_unverified_context()


def _token(client: dict) -> str:
    body = urlencode({"grant_type": "client_credentials", "scope": "urn:iam:myscopes", "resource": VCF_ROUTE}).encode()
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
    req = Request(VCF_ROUTE, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("MCP-Protocol-Version", "2025-06-18")
    req.add_header("X-CLIENT-TRANSACTION-ID", txn)
    if session:
        req.add_header("Mcp-Session-Id", session)
    try:
        with urlopen(req, timeout=45, context=_TLS) as resp:
            raw = resp.read().decode()
            return resp.status, raw, resp.headers.get("Mcp-Session-Id")
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


def audit_line(txn: str, since: float) -> str:
    """The AI Gateway's own log line for this transaction, read through the Kubernetes door."""
    try:
        pods = k8s_call("k8s_list_pods", {"namespace": "ssp"}, timeout=40).get("pods") or []
    except RuntimeError as exc:
        return f"Could not list the AgentMinder pods: {str(exc)[:200]}"
    gateway = next((p["name"] for p in pods if str(p.get("name", "")).startswith("ssp-ssp-aigateway-")), None)
    if not gateway:
        return "No AI Gateway pod was found in namespace ssp."
    for _ in range(6):
        try:
            log = k8s_call("k8s_pod_logs", {"namespace": "ssp", "name": gateway, "tail": 200}, timeout=40).get("log") or ""
        except RuntimeError as exc:
            return f"The Kubernetes door may not read the AI Gateway log: {str(exc)[:220]}"
        hits = [_mask(line) for line in log.splitlines() if txn in line]
        if hits:
            return "\n".join(hits[-3:])
        if time.time() - since > 60:
            break
        time.sleep(5)
    return f"No line with transaction id {txn} in the last 200 lines of {gateway}."


def _mask(line: str) -> str:
    line = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<masked>", line)
    return re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "<masked-jwt>", line)


def main() -> int:
    read_audit = "--read-audit" in sys.argv[1:]
    client = json.loads(CLIENTS.read_text(encoding="utf-8"))[AGENT]
    txn = str(uuid.uuid4())
    started = time.time()
    print(f"{time.strftime('%H:%M:%S', time.gmtime())} UTC. The VCF diagnostic agent asks AgentMinder for its token.")
    token = _token(client)
    status, raw, session = _rpc(token, txn, "initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "deny-beat", "version": "1"}})
    if status != 200:
        print(f"The gateway refused the session itself: HTTP {status}. {raw[:200]}")
        return 1
    _rpc(token, txn, "notifications/initialized", {}, session, rid=None)
    status, raw, _ = _rpc(token, txn, "tools/list", {}, session, rid=2)
    tools = [t.get("name") for t in ((_data(raw).get("result") or {}).get("tools") or []) if isinstance(t, dict)]
    print(f"Tools AgentMinder lists for this agent: {', '.join(tools) or 'none'}.")
    print(f"The agent calls {TOOL} on {TARGET_VM}. Transaction id {txn}.")
    status, raw, _ = _rpc(token, txn, "tools/call", {"name": TOOL, "arguments": {"vm": TARGET_VM}}, session, rid=3)
    doc = _data(raw)
    error = doc.get("error") if isinstance(doc.get("error"), dict) else None
    result = doc.get("result") if isinstance(doc.get("result"), dict) else None
    refused = status in (401, 403) or bool(error) or bool(result and result.get("isError"))
    reason = (error or {}).get("message") or (raw[:200] if status != 200 else json.dumps(result)[:200])
    if refused and not reason.strip():
        reason = "The gateway did not forward the call to the VCF door."
    if refused:
        print(f"DENIED. HTTP {status}. {reason}")
    else:
        print(f"NOT DENIED. HTTP {status}. The gateway forwarded the call. {reason}")
    if read_audit:
        print("AgentMinder AI Gateway audit line:")
        print(audit_line(txn, started))
    else:
        print(f"The gateway's audit line for transaction {txn} is read by hand by IT or Number One (Security INS-284).")
    return 0 if refused else 1


if __name__ == "__main__":
    raise SystemExit(main())
