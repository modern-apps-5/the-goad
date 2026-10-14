#!/usr/bin/env python3
"""Incident enrichment harness.

One orchestrator and three specialists. Each calls Qwen
qwen3.5:122b-a10b on the DGX, one call at a time. Jev chooses the
route. The write-up is posted to the Zammad ticket.

Configuration is environment variables. Copy .env.example to .env.
Do not commit .env.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.envfile import load_env  # noqa: E402
from orchestrator.jev import ask as jev_ask  # noqa: E402
from orchestrator.k8s import call as k8s_call  # noqa: E402
from orchestrator.qwen import complete as qwen_complete  # noqa: E402
from orchestrator.skill_loader import load_skill  # noqa: E402
from orchestrator.specialists import (  # noqa: E402
    logs_prompt,
    orchestrator_prompt,
    platform_prompt,
    writer_prompt,
)

NS = "metal-music-store"
REPORT_PATH = Path(__file__).resolve().parent / "last-run.json"
HOUSE_TOKENS = Path(__file__).resolve().parent / "house-tokens.jsonl"

JEV_OPTIONS = {
    "database-outage": "Category database outage. Severity P1. Route the DB and platform team. Action: restore Postgres.",
    "cart-latency": "Category cart latency. Severity P2. Route the app team. Action: remove the added cart delay.",
    "store-bug": "Category application bug. Severity P2. Route the store team. Action: roll the store back.",
    "unknown": "Category unknown. Severity P3. Route on-call. Action: keep investigating.",
}


def kube_text(tool: str, args: dict, *, write: bool = False) -> str:
    try:
        out = k8s_call(tool, args, write=write, timeout=40)
        return json.dumps(out, ensure_ascii=False)[-4000:]
    except RuntimeError as exc:
        return f"mcp failed: {exc}"[:4000]


def store_status() -> dict:
    load_env()
    store_url = os.environ.get("STORE_URL", "https://${STORE_HOST}/")
    # The lab ingress certificate is signed by the lab CA, which is not in
    # the public trust store on this machine. The check still needs the
    # HTTP status, so hostname verification is off for this URL only.
    req = urllib.request.Request(store_url, method="GET")
    ctx = ssl._create_unverified_context()
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            body = resp.read(200)
            return {
                "url": store_url,
                "status": resp.status,
                "bytes": len(body),
                "ms": int((time.perf_counter() - started) * 1000),
            }
    except urllib.error.HTTPError as exc:
        return {"url": store_url, "status": exc.code, "ms": int((time.perf_counter() - started) * 1000), "error": "HTTP"}
    except OSError as exc:
        return {"url": store_url, "status": None, "error": type(exc).__name__}


def gather() -> dict:
    pods = kube_text("k8s_list_pods", {"namespace": NS})
    store_pod = "music-store-1"
    try:
        listed = json.loads(pods)
        for row in listed.get("pods") or []:
            name = str(row.get("name") or "")
            if name.startswith("music-store-1"):
                store_pod = name
                break
    except json.JSONDecodeError:
        pass
    return {
        "store": store_status(),
        "pods": pods,
        "events": kube_text("k8s_events", {"namespace": NS}),
        "store_log": kube_text("k8s_pod_logs", {"namespace": NS, "name": store_pod, "tail": 40}),
        "postgres_log": kube_text("k8s_pod_logs", {"namespace": NS, "name": "postgres-demo", "tail": 40}),
    }


def qwen_call(
    role: str, prompt: str, calls: list[dict], max_tokens: int = 500, reasoning_effort: str | None = None
) -> str:
    if calls:
        gap = time.time() - calls[-1]["ended"]
        if gap < 0:
            raise RuntimeError("Qwen calls overlapped")
    started = time.time()
    perf = time.perf_counter()
    _folder, _version, skill = load_skill(role)
    messages = []
    if skill:
        messages.append({"role": "system", "content": skill})
    messages.append({"role": "user", "content": prompt})
    # The gate keeps the GPU for a live demo and refuses bulk.
    # This run is that demo, so it uses the demo class.
    text, tokens_in, tokens_out, model = qwen_complete(
        messages,
        max_tokens=max_tokens,
        timeout=240,
        temperature=0.2,
        model="qwen3.5:122b-a10b",
        traffic_class="demo",
        reasoning_effort=reasoning_effort,
    )
    ended = time.time()
    calls.append(
        {
            "role": role,
            "model": model,
            "started": started,
            "ended": ended,
            "ms": int((time.perf_counter() - perf) * 1000),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "chars": len(text or ""),
        }
    )
    print(f"qwen {role} {calls[-1]['ms']} ms model {model}")
    if tokens_in is not None or tokens_out is not None:
        row = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "dgx",
            "model": model,
            "caller": role,
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
        }
        with HOUSE_TOKENS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
    return (text or "").strip()


def jev_decision(evidence: str) -> dict:
    question = {
        "type": "choice",
        "instructions": (
            "A metal music store on the lab cluster is failing. "
            "Choose exactly one route. Use the evidence. "
            + evidence[:3500]
        ),
        "criteria": JEV_OPTIONS,
    }
    row = jev_ask("incident-enrichment", "store incident on VCF lab VKS", question, timeout=60)
    answer = (((row.get("response") or {}).get("answers") or {}).get("q") or {})
    return {
        "decider": row.get("decider"),
        "error": row.get("error"),
        "choice": answer.get("choice"),
        "confidence": answer.get("confidence"),
        "model": (row.get("response") or {}).get("model"),
    }


def zammad_request(method: str, path: str, payload: dict | None) -> tuple[int, str]:
    load_env()
    base = (os.environ.get("ZAMMAD_URL") or "").rstrip("/")
    token = os.environ.get("ZAMMAD_TOKEN") or ""
    if not base or not token:
        return 0, "Zammad URL or token is unset"
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Token token={token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500].replace(token, "[redacted]")
        return exc.code, body
    except OSError as exc:
        return 0, type(exc).__name__


def open_ticket(store: dict, title: str = "Metal Music Store slow: checkout and catalog pages taking 10+ seconds") -> dict:
    status, body = zammad_request(
        "POST",
        "/api/v1/tickets",
        {
            "title": title,
            "group": "Users",
            "customer_id": "guess:oncall@metal-store.lab",
            "article": {
                "subject": title,
                "body": (
                    "Checkout and catalog pages are taking 10 seconds or more. The store is still up. "
                    f"Store check: HTTP {store.get('status')} in {store.get('ms')} ms."
                ),
                "type": "note",
                "internal": False,
            },
        },
    )
    ticket_id = None
    if status in (200, 201):
        try:
            ticket_id = json.loads(body).get("id")
        except json.JSONDecodeError:
            ticket_id = None
    return {"status": status, "ticket_id": ticket_id, "body": body[:400]}


def post_writeup(ticket_id: int, note: str, choice: str | None) -> dict:
    status, body = zammad_request(
        "POST",
        "/api/v1/ticket_articles",
        {
            "ticket_id": ticket_id,
            "subject": "Enrichment",
            "body": note,
            "type": "note",
            "internal": False,
            "sender": "Agent",
        },
    )
    priority = "3 high" if choice == "database-outage" else "2 normal"
    updated, update_body = zammad_request(
        "PUT",
        f"/api/v1/tickets/{ticket_id}",
        {"priority": priority, "group": "Users"},
    )
    tag_status = None
    if choice:
        tag_status, _tag_body = zammad_request(
            "POST",
            "/api/v1/tags/add",
            {"object": "Ticket", "o_id": ticket_id, "item": choice},
        )
    return {
        "article_status": status,
        "article_body": body[:300],
        "update_status": updated,
        "update_body": update_body[:200],
        "tag_status": tag_status,
        "priority": priority,
    }


def serial_ok(calls: list[dict]) -> bool:
    for earlier, later in zip(calls, calls[1:]):
        if later["started"] < earlier["ended"]:
            return False
    return True


def run() -> dict:
    load_env()
    evidence = gather()
    ticket = open_ticket(evidence["store"])
    calls: list[dict] = []
    packet = json.dumps(evidence, ensure_ascii=False)[:6000]
    brief = qwen_call("orchestrator", orchestrator_prompt(packet), calls)
    decision = jev_decision(brief + "\n" + packet[:2000])
    logs_note = qwen_call("logs-specialist", logs_prompt(brief, packet), calls)
    platform_note = qwen_call(
        "platform-specialist",
        platform_prompt(brief, evidence["pods"], evidence["events"]),
        calls,
    )
    choice = decision.get("choice") or "unknown"
    route = JEV_OPTIONS.get(choice, JEV_OPTIONS["unknown"])
    writeup = qwen_call(
        "writer-specialist",
        writer_prompt(choice, route, brief, logs_note, platform_note),
        calls,
    )
    posted = None
    if ticket.get("ticket_id"):
        posted = post_writeup(int(ticket["ticket_id"]), writeup, choice)
    report = {
        "store": evidence["store"],
        "jev": decision,
        "qwen": calls,
        "serial_ok": serial_ok(calls),
        "ticket": {"status": ticket.get("status"), "ticket_id": ticket.get("ticket_id")},
        "posted": posted,
        "writeup": writeup,
        "brief": brief,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    report = run()
    public = {
        "store": report["store"],
        "jev": report["jev"],
        "qwen_ms": [{c["role"]: c["ms"], "model": c["model"]} for c in report["qwen"]],
        "serial_ok": report["serial_ok"],
        "ticket": report["ticket"],
        "posted": {k: v for k, v in (report["posted"] or {}).items() if k != "article_body" and k != "update_body"},
    }
    print(json.dumps(public, indent=2))
    return 0 if report["serial_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
