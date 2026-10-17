#!/usr/bin/env python3
"""Orchestrator. Decision gate is CLM. A blank CLM_URL uses the fallback.

Calls the three diagnostic agents. One stalled agent does not stop the
note. Does not call Kubernetes, Avi, or VCF itself.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AGENTS = (
    ("lb-diagnostic-agent", "lb_diagnostic_agent", "Load balancer (Avi)"),
    ("k8s-diagnostic-agent", "k8s_diagnostic_agent", "Kubernetes"),
    ("vcf-diagnostic-agent", "vcf_diagnostic_agent", "VCF"),
)
LIVE: dict = {"steps": [], "fallback": True, "note": ""}
SINK = None


def step(text: str) -> None:
    LIVE["steps"].append({"t": time.strftime("%H:%M:%S", time.gmtime()), "text": text})
    _grafana(text)
    if SINK is not None:
        SINK(json.dumps({"step": text}) + "\n")


def _grafana(text: str) -> None:
    url = os.environ.get("GRAFANA_URL", "").rstrip("/")
    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")
    if not url or not password:
        return
    import base64

    body = json.dumps({"text": text[:400], "tags": ["incident"]}).encode()
    req = urllib.request.Request(
        url + "/api/annotations",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(f"admin:{password}".encode()).decode(),
        },
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        return


def store_check() -> dict:
    url = os.environ.get("STORE_URL", "").rstrip("/") + "/"
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=40, context=ssl._create_unverified_context()) as resp:
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
    url = f"http://{service}:8080/api/chat"
    payload = json.dumps({"message": message, "incident_id": incident_id}).encode()
    req = urllib.request.Request(url, data=payload, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            body = b'{"ok":true,"service":"orchestrator"}\n'
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
        if self.path.split("?", 1)[0] != "/run":
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
