#!/usr/bin/env python3
"""Tools for the incident response agent's chat, plus the live board feed.

The Tanzu cell can reach this app, Jev, the DGX, and the domain agents.
It cannot reach the helpdesk. When a chat asks for the latest ticket,
this process sets need_ticket. The company watch on agents-machine reads
the latest open ticket and posts that one ticket here. Start does not.
The helpdesk write stays queued. The watch pulls GET /live and writes
the note. POST /reset forgets the last run so the board starts empty.

Nothing in this file is a Kubernetes or VCF grant.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.enrich import run_prepared  # noqa: E402
from orchestrator.reasoning import PATH as REASONING_PATH  # noqa: E402

SNAPSHOT = Path(os.environ.get("INCIDENT_SNAPSHOT") or ROOT / "incident-snapshot.json")
NEED = SNAPSHOT.with_name("need-ticket")
_LOCK = threading.Lock()
_RUNNING = False
_EPOCH = ""
_POLLS = 0
# Six status calls, each waiting up to 25s, cover one pass of the three
# domain agents. A longer poll loop filled the model window and Qwen
# answered 400. The seventh call returns immediately and says stop.
_MAX_POLLS = 6
_STATUS_WAIT = 25


def _token() -> str:
    return os.environ.get("MCP_TOKEN") or ""


def _authorized(header: str | None) -> bool:
    expected = _token()
    if not expected or not header or not header.lower().startswith("bearer "):
        return False
    got = header.split(" ", 1)[1].strip()
    return hmac.compare_digest(got, expected)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _audience() -> dict:
    doc = _read_json(REASONING_PATH) or {}
    if _EPOCH and str(doc.get("started_at") or "") < _EPOCH:
        return {"state": "running", "ticket_number": "", "title": "", "assessment": "",
                "jev_agents": None, "agents_called": [], "jev_route": None, "enrichment": "",
                "error": None, "timeline": [], "say": "Enrichment is starting."}
    audience = doc.get("audience") or {}
    return {
        "state": audience.get("state") or doc.get("state") or "idle",
        "ticket_number": audience.get("ticket_number") or "",
        "title": audience.get("title") or "",
        "assessment": audience.get("assessment") or "",
        "jev_agents": audience.get("jev_agents"),
        "agents_called": audience.get("agents_called") or [],
        "jev_route": audience.get("jev_route"),
        "enrichment": audience.get("enrichment") or "",
        "error": audience.get("error"),
        "timeline": doc.get("timeline") or [],
    }


def _worker(snapshot: dict) -> None:
    global _RUNNING
    try:
        run_prepared(snapshot)
    except Exception as exc:
        # run_prepared already records a failed reasoning file when it can.
        print(f"enrichment failed: {type(exc).__name__}", flush=True)
    finally:
        with _LOCK:
            _RUNNING = False


def _ask_for_ticket() -> dict | None:
    """Wait until the company watch posts the latest open ticket."""
    if SNAPSHOT.exists():
        SNAPSHOT.unlink()
    NEED.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "\n", encoding="utf-8")
    deadline = time.time() + 40
    while time.time() < deadline:
        snapshot = _read_json(SNAPSHOT)
        if snapshot and snapshot.get("id"):
            return snapshot
        time.sleep(1)
    NEED.unlink(missing_ok=True)
    return None


def _compact(*, stop: bool) -> dict:
    """Short status. The chat keeps every tool result, so this stays small."""
    audience = _audience()
    agents = []
    for row in audience.get("agents_called") or []:
        if not isinstance(row, dict):
            continue
        agents.append({
            "agent": row.get("agent"),
            "valid": row.get("valid"),
            "finding": str(row.get("finding") or "")[:300],
        })
    route = audience.get("jev_route")
    route_brief = None
    if isinstance(route, dict):
        route_brief = {key: route.get(key) for key in ("choice", "confidence", "used", "priority", "group")}
    jev = audience.get("jev_agents")
    jev_brief = None
    if isinstance(jev, dict):
        jev_brief = {key: jev.get(key) for key in ("choice", "confidence", "used", "rule")}
    say = (
        "Stop. Do not call enrich_status again. Reply to the audience from this object."
        if stop else
        f"Still running. Calls left after this one: {max(0, _MAX_POLLS - _POLLS)}."
    )
    return {
        "state": audience.get("state") or "running",
        "stop": stop,
        "ticket_number": audience.get("ticket_number") or "",
        "title": audience.get("title") or "",
        "assessment": str(audience.get("assessment") or "")[:400],
        "jev_agents": jev_brief,
        "agents": agents,
        "route": route_brief,
        "enrichment": str(audience.get("enrichment") or "")[:1500 if stop else 240],
        "error": audience.get("error"),
        "say": say,
    }


def _start() -> dict:
    global _RUNNING, _EPOCH, _POLLS
    with _LOCK:
        if _RUNNING:
            return {**_compact(stop=False), "say": "Enrichment is already running. Call enrich_status at most 6 times."}
        _RUNNING = True
        _POLLS = 0
        _EPOCH = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snapshot = _ask_for_ticket()
    if not snapshot:
        with _LOCK:
            _RUNNING = False
        return {
            "state": "failed",
            "error": "The latest open ticket could not be read.",
            "say": "The latest open ticket could not be read.",
        }
    threading.Thread(target=_worker, args=(snapshot,), daemon=True).start()
    return {
        "state": "started",
        "stop": False,
        "say": "Enrichment started. Call enrich_status at most 6 times. Stop when stop is true.",
    }


def _clear() -> tuple[int, dict]:
    """Forget the last run so the live board starts empty. Refuses while a run is going."""
    global _EPOCH
    with _LOCK:
        if _RUNNING:
            return 409, {"ok": False, "error": "enrichment is running"}
        _EPOCH = ""
        for path in (REASONING_PATH, SNAPSHOT, NEED):
            path.unlink(missing_ok=True)
    return 200, {"ok": True, "cleared": True}


def _status() -> dict:
    global _POLLS
    _POLLS += 1
    if _POLLS > _MAX_POLLS:
        body = _compact(stop=True)
        if body.get("state") not in ("done", "failed"):
            body["state"] = "done"
        return body
    deadline = time.time() + _STATUS_WAIT
    while time.time() < deadline:
        with _LOCK:
            running = _RUNNING
        if not running or _audience().get("state") in ("done", "failed"):
            return _compact(stop=True)
        time.sleep(1)
    stop = _POLLS >= _MAX_POLLS
    body = _compact(stop=stop)
    if stop and body.get("state") not in ("done", "failed"):
        body["state"] = "done"
    return body


def _tool(name: str, args: dict) -> dict:
    if name == "enrich_latest_incident":
        return _start()
    if name == "enrich_status":
        return _status()
    raise KeyError(name)


def _rpc(body: dict) -> dict | None:
    req_id = body.get("id")
    method = body.get("method") or ""
    if req_id is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "incident-live", "version": "2026-10-12"}}
    elif method in ("notifications/initialized", "ping"):
        result = {}
    elif method == "tools/list":
        result = {"tools": [
            {"name": "enrich_latest_incident",
             "description": "Start enrichment of the latest open Metal Music Store incident. No arguments. Call once.",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "enrich_status",
             "description": "One enrichment snapshot. Call at most 6 times. When stop is true, reply and do not call again.",
             "inputSchema": {"type": "object", "properties": {}}},
        ]}
    elif method == "tools/call":
        params = body.get("params") or {}
        try:
            payload = _tool(str(params.get("name") or ""), params.get("arguments") or {})
        except KeyError:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "unknown tool"}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32603, "message": f"{type(exc).__name__}: {str(exc)[:240]}"}}
        result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict | None, content_type: str = "application/json") -> None:
        body = b"" if payload is None else json.dumps(payload, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _denied(self) -> None:
        self._send(401, {"ok": False, "error": "unauthorized"})

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send(200, {"ok": True})
            return
        if not _authorized(self.headers.get("Authorization")):
            self._denied()
            return
        if path == "/live":
            doc = _read_json(REASONING_PATH) or {"state": "idle", "timeline": [], "components": []}
            doc["need_ticket"] = NEED.is_file()
            self._send(200, doc)
            return
        self._send(404, {"ok": False})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not _authorized(self.headers.get("Authorization")):
            self._denied()
            return
        if path == "/incident":
            try:
                doc = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, {"ok": False, "error": "bad json"})
                return
            if not isinstance(doc, dict) or not doc.get("id"):
                self._send(400, {"ok": False, "error": "missing ticket id"})
                return
            SNAPSHOT.write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
            NEED.unlink(missing_ok=True)
            self._send(200, {"ok": True, "id": doc["id"], "number": doc.get("number")})
            return
        if path == "/reset":
            self._send(*_clear())
            return
        if path == "/mcp":
            try:
                body = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, {"ok": False, "error": "bad json"})
                return
            reply = _rpc(body if isinstance(body, dict) else {})
            if reply is None:
                self.send_response(202)
                self.end_headers()
                return
            self._send(200, reply)
            return
        self._send(404, {"ok": False})

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    if not _token():
        raise SystemExit("MCP_TOKEN is unset")
    port = int(os.environ.get("PORT") or "8080")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
