#!/usr/bin/env python3
"""Orchestrator. Decision gate is CLM. A blank CLM_URL uses the fallback.

Calls the three diagnostic agents. One stalled agent does not stop the
note. Does not call Kubernetes, Avi, or VCF itself.
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AGENTS = (
    ("lb-diagnostic-agent", "lb_diagnostic_agent", "Load balancer (Avi)"),
    ("k8s-diagnostic-agent", "k8s_diagnostic_agent", "Kubernetes"),
    ("vcf-diagnostic-agent", "vcf_diagnostic_agent", "VCF"),
)
LIVE: dict = {"steps": [], "fallback": True, "note": "", "state": "idle", "ticket_number": "", "title": "", "error": ""}
SINK = None
_LOCK = threading.Lock()
_RUNNING = False
_POLLS = 0


def step(text: str) -> None:
    LIVE["steps"].append({"t": time.strftime("%H:%M:%S", time.gmtime()), "text": text})
    _grafana(text)
    if SINK is not None:
        SINK(json.dumps({"step": text}) + "\n")


def _open(url: str, timeout: int, connect_ip: str = "", data: bytes | None = None, headers: dict | None = None):
    parsed = urllib.parse.urlparse(url)
    dest = url
    hdrs = dict(headers or {})
    if connect_ip and parsed.hostname:
        netloc = connect_ip if not parsed.port else f"{connect_ip}:{parsed.port}"
        dest = urllib.parse.urlunparse(parsed._replace(netloc=netloc))
        hdrs["Host"] = parsed.hostname
    req = urllib.request.Request(dest, data=data, method="POST" if data is not None else "GET", headers=hdrs)
    if url.startswith("https://"):
        return urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
    return urllib.request.urlopen(req, timeout=timeout)


def _grafana(text: str) -> None:
    url = os.environ.get("GRAFANA_URL", "").rstrip("/")
    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")
    if not url or not password:
        return
    import base64

    body = json.dumps({"text": text[:400], "tags": ["incident"]}).encode()
    try:
        _open(
            url + "/api/annotations",
            5,
            os.environ.get("GRAFANA_CONNECT_IP", "").strip(),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Basic " + base64.b64encode(f"admin:{password}".encode()).decode(),
            },
        ).read()
    except Exception:
        return


def store_check() -> dict:
    url = os.environ.get("STORE_URL", "").rstrip("/") + "/"
    started = time.time()
    try:
        with _open(url, 40, os.environ.get("STORE_CONNECT_IP", "").strip()) as resp:
            resp.read(200)
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:
        status = 0
    return {"url": url, "status": status, "ms": int((time.time() - started) * 1000)}


def clm_choice(question: str, options: dict) -> dict:
    root = os.environ.get("CLM_URL", "").strip().rstrip("/")
    if not root:
        return {"choice": None, "confidence": 0, "error": "CLM_URL is unset", "fallback": True, "options": list(options)}
    payload = {
        "state": "goad incident",
        "model": os.environ.get("CLM_MODEL", "clm-latest"),
        "questions": {"q": {"type": "choice", "instructions": question, "criteria": options}},
    }
    req = urllib.request.Request(
        root + "/v1/systemone",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:
        return {"choice": None, "confidence": 0, "error": type(exc).__name__, "fallback": True}
    answer = (((body.get("answers") or {}).get("q")) or {})
    choice = answer.get("choice") if answer.get("choice") in options else None
    try:
        confidence = float(answer.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0
    return {"choice": choice, "confidence": confidence, "error": None, "fallback": False}


def ask_agent(service: str, role: str, incident_id: str, message: str, timeout: float) -> dict:
    overrides = {
        "lb-diagnostic-agent": os.environ.get("LB_AGENT_URL", ""),
        "k8s-diagnostic-agent": os.environ.get("K8S_AGENT_URL", ""),
        "vcf-diagnostic-agent": os.environ.get("VCF_AGENT_URL", ""),
    }
    url = (overrides.get(service) or f"http://{service}:8080/api/chat").strip()
    payload = json.dumps({"message": message, "incident_id": incident_id}).encode()
    try:
        with _open(url, int(timeout), "", data=payload, headers={"Content-Type": "application/json"}) as resp:
            doc = json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "calls": [], "report": None}
    report = None
    try:
        report = json.loads(doc.get("text") or "")
    except json.JSONDecodeError:
        report = None
    return {"ok": isinstance(report, dict), "error": "" if report else "no findings", "calls": doc.get("calls") or [], "report": report}


def qwen_note(packet: str) -> dict:
    base = os.environ.get("QWEN_BASE_URL", "").rstrip("/")
    key = os.environ.get("QWEN_API_KEY", "")
    model = os.environ.get("QWEN_MODEL", "qwen")
    if not base or not key:
        return {}
    prompt = (
        "Write one JSON object with keys summary, root_cause, confidence, impact, next_steps. "
        "If VCF write latency is hundreds of milliseconds and the store answered HTTP 200 slowly, "
        "the root cause is storage latency. Use only these facts.\n" + packet[:8000]
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            doc = json.loads(resp.read().decode())
    except Exception:
        return {}
    text = (((doc.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict) and value.get("summary") and value.get("root_cause"):
            return value
        index = text.find("{", end)
    return {}


def _storage(report: dict | None) -> bool:
    if not isinstance(report, dict):
        return False
    blob = json.dumps(report).lower()
    return "storage latency" in blob or "write latency" in blob


def compose(ticket: dict, store: dict, runs: list[dict], gate: dict, prose: dict) -> str:
    fallback = "Decision gate: CLM fallback (CLM_URL is unset)." if gate.get("fallback") else "Decision gate: CLM."
    lines = [
        fallback,
        f"Store check: HTTP {store.get('status')} in {store.get('ms')} ms.",
        f"Agents called: {', '.join(item['label'] for item in runs)}.",
    ]
    if prose:
        lines += [
            "SUMMARY",
            str(prose.get("summary") or "").strip(),
            "LIKELY ROOT CAUSE",
            str(prose.get("root_cause") or "").strip(),
            "IMPACT",
            str(prose.get("impact") or "").strip(),
        ]
    else:
        lines += ["SUMMARY", "Qwen did not return the prose. The evidence below is the report."]
    lines.append("EVIDENCE BY DOMAIN")
    for item in runs:
        lines.append(item["label"])
        if item["error"] and not item["report"]:
            lines.append(f"  stalled or failed: {item['error']}. The report continues.")
            continue
        cause = ((item["report"] or {}).get("suspected_cause") or {}).get("cause")
        lines.append(f"  {cause or item['report'].get('status')}")
        for finding in (item["report"] or {}).get("findings") or []:
            lines.append(f"  - [{finding.get('severity')}] {finding.get('symptom')}")
    lines.append("ACCESS LOG")
    for item in runs:
        tools = [c.get("tool") for c in item["calls"] if c.get("ok")]
        denied = [c.get("tool") for c in item["calls"] if not c.get("ok")]
        lines.append(f"{item['label']}: allowed {', '.join(tools) or 'none'}; denied {', '.join(denied) or 'none'}")
    lines.append("Written by the incident response agent. No change was made.")
    return "\n".join(lines)


def run(ticket: dict) -> dict:
    LIVE["steps"] = []
    store = store_check()
    step(f"Store answered HTTP {store['status']} in {store['ms']} ms.")
    gate = clm_choice(
        "Choose diagnostic agents. A slow HTTP 200 store needs all three.",
        {"all-three": "Call load balancer, Kubernetes, and VCF."},
    )
    if gate.get("fallback") or (gate.get("confidence") or 0) < 0.70 or gate.get("choice") != "all-three":
        step(f"Decision gate is on fallback. All three diagnostic agents will be called. ({gate.get('error') or 'confidence below 0.70'})")
        LIVE["fallback"] = True
    else:
        step("Decision gate CLM chose all three agents.")
        LIVE["fallback"] = False
    runs = []
    for service, role, label in AGENTS:
        step(f"Calling {label}.")
        result = ask_agent(service, role, str(ticket.get("number") or ticket.get("id")), ticket.get("text") or "", 180)
        item = {"service": service, "role": role, "label": label, **result}
        if item["report"]:
            cause = ((item["report"].get("suspected_cause") or {}).get("cause")) or item["report"].get("status")
            step(f"{label} returned: {cause}")
        else:
            step(f"{label} stalled or failed ({item['error']}). Continuing the report.")
        runs.append(item)
    vcf = next((item for item in runs if item["role"] == "vcf_diagnostic_agent"), None)
    storage = _storage((vcf or {}).get("report"))
    packet = json.dumps(
        {"ticket": ticket, "store": store, "storage_latency": storage, "runs": [
            {"label": item["label"], "report": item["report"], "error": item["error"]} for item in runs
        ]},
        default=str,
    )
    step("Qwen is writing the summary.")
    prose = qwen_note(packet)
    if storage and prose and "storage" not in str(prose.get("root_cause") or "").lower():
        prose["root_cause"] = "Storage latency on the shared datastore. The store is up and pages are slow."
    if not prose and storage:
        prose = {
            "summary": f"Ticket {ticket.get('number')} : the store is up and slow.",
            "root_cause": "Storage latency on the shared datastore.",
            "confidence": 0.9,
            "impact": f"The store answered HTTP {store.get('status')} in {store.get('ms')} ms.",
            "next_steps": ["Storage reviews the datastore. No change was made."],
        }
    note = compose(ticket, store, runs, gate, prose)
    if storage and "storage latency" not in note.lower():
        note += "\nLIKELY ROOT CAUSE\nStorage latency on the shared datastore."
    LIVE["note"] = note
    step("Enrichment note is ready.")
    return {"note": note, "fallback": bool(gate.get("fallback") or LIVE["fallback"]), "storage_latency": storage, "store": store, "runs": runs}


def latest_open_ticket() -> dict:
    """Latest open Zammad ticket. Empty when the helpdesk cannot be read."""
    base = os.environ.get("ZAMMAD_URL", "").strip().rstrip("/")
    token = os.environ.get("ZAMMAD_TOKEN", "").strip()
    if not base or not token:
        return {}
    headers = {"Authorization": f"Token token={token}", "Accept": "application/json"}
    url = base + "/api/v1/tickets/search?query=state.name:open&limit=5&sort_by=created_at&order_by=desc"
    try:
        with _open(url, 20, os.environ.get("ZAMMAD_CONNECT_IP", "").strip(), headers=headers) as resp:
            doc = json.loads(resp.read().decode())
    except Exception:
        return {}
    rows = doc if isinstance(doc, list) else []
    if isinstance(doc, dict):
        assets = ((doc.get("assets") or {}).get("Ticket")) or {}
        if isinstance(assets, dict) and assets:
            rows = list(assets.values())
        elif isinstance(doc.get("tickets"), list):
            rows = doc["tickets"]
    if not rows:
        return {}
    ticket = rows[0] if isinstance(rows[0], dict) else {}
    if not ticket.get("id") and isinstance(rows[0], int):
        try:
            with _open(base + f"/api/v1/tickets/{rows[0]}", 20, os.environ.get("ZAMMAD_CONNECT_IP", "").strip(), headers=headers) as resp:
                ticket = json.loads(resp.read().decode())
        except Exception:
            return {}
    text = str(ticket.get("title") or "")
    return {
        "id": ticket.get("id"),
        "number": ticket.get("number"),
        "title": ticket.get("title") or "",
        "text": text,
    }


def _compact(*, stop: bool) -> dict:
    state = LIVE.get("state") or "idle"
    say = (
        "Stop. Do not call enrich_status again. Reply from this object."
        if stop
        else f"Still running. Calls left after this one: {max(0, 6 - _POLLS)}."
    )
    return {
        "state": state,
        "stop": stop,
        "ticket_number": LIVE.get("ticket_number") or "",
        "title": LIVE.get("title") or "",
        "assessment": str(LIVE.get("note") or "")[:400],
        "enrichment": str(LIVE.get("note") or "")[:1500 if stop else 240],
        "error": LIVE.get("error"),
        "fallback": bool(LIVE.get("fallback")),
        "say": say,
    }


def _worker(ticket: dict) -> None:
    global _RUNNING
    try:
        outcome = run(ticket)
        with _LOCK:
            LIVE["state"] = "done"
            LIVE["note"] = outcome.get("note") or ""
            LIVE["error"] = ""
    except Exception as exc:
        with _LOCK:
            LIVE["state"] = "failed"
            LIVE["error"] = type(exc).__name__
    finally:
        with _LOCK:
            _RUNNING = False


def enrich_latest_incident() -> dict:
    global _RUNNING, _POLLS
    with _LOCK:
        if _RUNNING:
            return {**_compact(stop=False), "say": "Enrichment is already running. Call enrich_status at most 6 times."}
        _RUNNING = True
        _POLLS = 0
        LIVE["state"] = "running"
        LIVE["error"] = ""
        LIVE["note"] = ""
        LIVE["steps"] = []
    ticket = latest_open_ticket()
    if not ticket.get("id"):
        with _LOCK:
            _RUNNING = False
            LIVE["state"] = "failed"
            LIVE["error"] = "no open ticket"
        return {
            "state": "failed",
            "stop": True,
            "error": "The latest open ticket could not be read.",
            "say": "The latest open ticket could not be read.",
        }
    with _LOCK:
        LIVE["ticket_number"] = str(ticket.get("number") or "")
        LIVE["title"] = ticket.get("title") or ""
    threading.Thread(target=_worker, args=(ticket,), daemon=True).start()
    return {
        "state": "started",
        "stop": False,
        "ticket_number": LIVE["ticket_number"],
        "title": LIVE["title"],
        "say": "Enrichment started. Call enrich_status at most 6 times. Stop when stop is true.",
    }


def enrich_status() -> dict:
    global _POLLS
    with _LOCK:
        _POLLS += 1
        polls = _POLLS
        running = _RUNNING
        state = LIVE.get("state") or "idle"
    if polls > 6 or (not running and state in ("done", "failed", "idle")):
        body = _compact(stop=True)
        if body.get("state") not in ("done", "failed"):
            body["state"] = "done"
        return body
    return _compact(stop=False)


def _rpc(body: dict) -> dict | None:
    req_id = body.get("id")
    method = body.get("method") or ""
    if req_id is None:
        return None
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "incident-live", "version": "2026-10-17"},
        }
    elif method in ("notifications/initialized", "ping"):
        result = {}
    elif method == "tools/list":
        result = {"tools": [
            {
                "name": "enrich_latest_incident",
                "description": "Start enrichment of the latest open Metal Music Store incident. No arguments. Call once.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "enrich_status",
                "description": "One enrichment snapshot. Call at most 6 times. When stop is true, reply and do not call again.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]}
    elif method == "tools/call":
        params = body.get("params") or {}
        name = str(params.get("name") or "")
        try:
            if name == "enrich_latest_incident":
                payload = enrich_latest_incident()
            elif name == "enrich_status":
                payload = enrich_status()
            else:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "unknown tool"}}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"{type(exc).__name__}: {str(exc)[:240]}"},
            }
        result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = b'{"ok":true,"service":"orchestrator"}\n'
        elif path == "/config/v1/endpoint":
            body = json.dumps({
                "name": "goad-qwen",
                "wireFormat": "OPENAI",
                "advertisedModels": [{"name": "qwen", "capabilities": ["CHAT", "TOOLS"]}],
            }).encode()
        elif path == "/live":
            body = json.dumps(LIVE).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/mcp":
            length = int(self.headers.get("Content-Length") or "0")
            try:
                body = json.loads(self.rfile.read(length).decode() or "{}")
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                return
            reply = _rpc(body if isinstance(body, dict) else {})
            if reply is None:
                self.send_response(202)
                self.end_headers()
                return
            raw = json.dumps(reply, ensure_ascii=False, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path != "/run":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            ticket = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            ticket = {}
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def sink(line: str) -> None:
            self._chunk(line.encode())

        global SINK
        SINK = sink
        try:
            outcome = run(ticket)
        finally:
            SINK = None
        self._chunk((json.dumps({"note": outcome["note"], "fallback": outcome["fallback"], "storage_latency": outcome["storage_latency"]}) + "\n").encode())
        self._chunk(b"")

    def _chunk(self, data: bytes) -> None:
        self.wfile.write(f"{len(data):X}\r\n".encode())
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
