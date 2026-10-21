#!/usr/bin/env python3
"""One diagnostic agent. Runs its skill's tool steps through AgentMinder.

Qwen turns the tool results into the findings object. If Qwen does not
return that object, the tool results still become a findings object so
the incident report can be finished.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import door

NS = "metal-music-store"
def _skill_text() -> str:
    candidates = (
        Path("/skills/SKILL.md"),
        Path(__file__).resolve().parent / "skills" / "SKILL.md",
    )
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def qwen(prompt: str, timeout: int = 90) -> str:
    base = os.environ.get("QWEN_BASE_URL", "").rstrip("/")
    key = os.environ.get("QWEN_API_KEY", "")
    model = os.environ.get("QWEN_MODEL", "qwen")
    if not base or not key:
        return ""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Reply with one JSON object and nothing else."},
            {"role": "user", "content": prompt[:12000]},
        ],
        "max_tokens": 900,
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
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            doc = json.loads(resp.read().decode())
    except Exception:
        return ""
    choice = (doc.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    return str(msg.get("content") or "")


def _json_object(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    index = (text or "").find("{")
    found = None
    while index != -1:
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict) and value.get("agent"):
            found = value
        index = text.find("{", end)
    return found


def steps_for(agent: str) -> list[tuple[str, dict]]:
    if agent == "lb_diagnostic_agent":
        return [("avi_latency", {})]
    if agent == "k8s_diagnostic_agent":
        ns = {"namespace": NS}
        return [
            ("k8s_list_deployments", dict(ns)),
            ("k8s_list_pods", dict(ns)),
            ("k8s_events", dict(ns)),
            ("k8s_pod_logs", {"namespace": NS, "name": "music-store-1", "tail": 80}),
        ]
    if agent == "vcf_diagnostic_agent":
        raw = os.environ.get("STORE_WORKER_VMS", "")
        vms = [part.strip() for part in raw.split(",") if part.strip()]
        return [("vcf_vm_disk_latency", {"vms": vms})]
    return []


def fallback(agent: str, incident_id: str, calls: list[dict]) -> dict:
    findings = []
    denied = []
    used = []
    cause = "No tool result named a cause."
    confidence = 0.4
    status = "degraded"
    for call in calls:
        used.append(call["tool"]) if call.get("ok") else denied.append(call["tool"])
        if not call.get("ok"):
            findings.append(
                {
                    "component": call["tool"],
                    "symptom": "The tool did not return a result.",
                    "evidence": {"tool": call["tool"], "raw_value": (call.get("error") or "")[:180]},
                    "severity": "warning",
                }
            )
            continue
        output = call.get("output")
        if call["tool"] == "vcf_vm_disk_latency" and isinstance(output, dict):
            sentence = str(output.get("finding") or "")
            writes = [
                row.get("write_latency_ms")
                for row in output.get("vms") or []
                if isinstance(row, dict) and isinstance(row.get("write_latency_ms"), (int, float))
            ]
            worst = max(writes) if writes else 0
            if worst >= 300 or "Write latency" in sentence:
                cause = sentence or f"Write latency is {worst:.0f} ms on the store VMs."
                confidence = 0.9
                status = "degraded"
                findings.append(
                    {
                        "component": "shared datastore",
                        "symptom": cause,
                        "evidence": {"tool": call["tool"], "raw_value": sentence or {"write_latency_ms": worst}},
                        "severity": "warning",
                    }
                )
            else:
                findings.append(
                    {
                        "component": "shared datastore",
                        "symptom": sentence or "Disk latency sample returned.",
                        "evidence": {"tool": call["tool"], "raw_value": (sentence or "ok")[:180]},
                        "severity": "info",
                    }
                )
        else:
            findings.append(
                {
                    "component": call["tool"],
                    "symptom": "Tool returned a result.",
                    "evidence": {"tool": call["tool"], "raw_value": _short(output)},
                    "severity": "info",
                }
            )
    if not findings:
        findings.append(
            {
                "component": agent,
                "symptom": "No tool ran.",
                "evidence": {"tool": used[0] if used else "none", "raw_value": "empty"},
                "severity": "warning",
            }
        )
    return {
        "agent": agent,
        "incident_id": incident_id,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "findings": findings[:6],
        "suspected_cause": {"cause": cause, "confidence": confidence},
        "recommended_action": "A person reads the evidence. No change was made.",
        "tools_used": used,
        "tools_denied": denied,
    }


def _short(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, default=str)
    return raw[:180]


def run(agent: str, incident_id: str, prompt: str) -> dict:
    calls = []
    for name, args in steps_for(agent):
        calls.append(door.call_tool(name, args))
    skill = _skill_text()
    ask = (
        f"Skill:\n{skill[:4000]}\n\nUser:\n{prompt[:1500]}\n\n"
        f"Tool results:\n{json.dumps(calls, default=str)[:7000]}\n\n"
        "Return the findings JSON object from the skill. "
        f'agent must be "{agent}". incident_id must be "{incident_id}". '
        "Every evidence.tool must be a tool in these results."
    )
    report = _json_object(qwen(ask))
    called = {c["tool"] for c in calls if c.get("ok")}
    if not _usable(report, agent, called):
        report = fallback(agent, incident_id, calls)
    return {"text": json.dumps(report), "calls": calls, "report": report}


def _usable(report: dict | None, agent: str, called: set[str]) -> bool:
    if not isinstance(report, dict) or report.get("agent") != agent:
        return False
    for finding in report.get("findings") or []:
        tool = ((finding or {}).get("evidence") or {}).get("tool")
        if tool not in called:
            return False
    return bool(report.get("findings"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] not in ("/health", "/"):
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"ok": True, "agent": os.environ.get("AGENT_ROLE", "")}).encode()
        self._send(200, body, "application/json")

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        agent = os.environ.get("AGENT_ROLE", "")
        incident_id = str(payload.get("incident_id") or "open")
        message = str(payload.get("message") or "")
        result = run(agent, incident_id, message)
        body = json.dumps({"text": result["text"], "calls": result["calls"]}).encode()
        self._send(200, body, "application/json")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
