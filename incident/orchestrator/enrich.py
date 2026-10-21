#!/usr/bin/env python3
"""Incident response agent: enrich one Zammad ticket.

Follows skills/incident_response_agent/SKILL.md:

1. Read the Zammad ticket.
2. Ask Jev which domain agents to call.
3. Call each chosen agent on Tanzu. Validate its findings with the
   Pydantic models in orchestrator/findings.py, and reject any finding
   that cites a tool the agent did not call.
4. Qwen writes the summary, root cause, impact, and next steps from the
   validated findings. The harness writes the evidence and access log.
5. Ask Jev for the route. Set priority, tags, and group. Post one note.

    python3 orchestrator/enrich.py --open          # open a bare ticket, then enrich it
    python3 orchestrator/enrich.py --ticket 5      # enrich ticket id 5

No token, key, or password is printed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator import tanzu_agents, topology  # noqa: E402
from orchestrator.envfile import load_env  # noqa: E402
from orchestrator.findings import Findings, validate  # noqa: E402
from orchestrator.jev import ask as jev_ask  # noqa: E402
from orchestrator.orchestrator import open_ticket, qwen_call, store_status, zammad_request  # noqa: E402
from orchestrator.incident_title import TITLE  # noqa: E402
from orchestrator.reasoning import Reasoning  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "last-enrichment.json"

AGENT_APPS = {
    "lb_diagnostic_agent": "lb-diagnostic-agent",
    "k8s_diagnostic_agent": "k8s-diagnostic-agent",
    "vcf_diagnostic_agent": "vcf-diagnostic-agent",
}
# Agent Builder's own memory tools. They are not MCP doors and AgentMinder
# does not gate them, so the access log leaves them out.
BUILDER_TOOLS = {"save_memory", "list_memories", "update_memory", "delete_memory", "search_memories"}
DOMAIN_TAG = {"lb_diagnostic_agent": "lb", "k8s_diagnostic_agent": "k8s", "vcf_diagnostic_agent": "vcf"}
DOMAIN_NAME = {
    "lb_diagnostic_agent": "Load balancer (Avi)",
    "k8s_diagnostic_agent": "Kubernetes",
    "vcf_diagnostic_agent": "VCF",
}

AGENT_SETS = {
    "all-three": (
        "Call the load balancer, Kubernetes, and VCF agents. "
        "Use this when pages are slow, or the fault could sit in any layer. "
        "A store that answers HTTP 200 while pages take many seconds is high response time on the load balancer, "
        "so the load balancer agent is required."
    ),
    "k8s-and-vcf": (
        "Call the Kubernetes and VCF agents. "
        "Use only when the store is down or the load balancer is not in the path. "
        "Do not pick this when the store answers HTTP 200 and pages are slow."
    ),
    "lb-and-k8s": "Call the load balancer and Kubernetes agents. Use when traffic or routing looks wrong and the platform is healthy.",
    "k8s-only": (
        "Call only the Kubernetes agent. "
        "Use when one application pod is crash-looping and the platform is not involved. "
        "Do not pick this when pages are slow and the database is still up."
    ),
}
SET_MEMBERS = {
    "all-three": ["lb_diagnostic_agent", "k8s_diagnostic_agent", "vcf_diagnostic_agent"],
    "k8s-and-vcf": ["k8s_diagnostic_agent", "vcf_diagnostic_agent"],
    "lb-and-k8s": ["lb_diagnostic_agent", "k8s_diagnostic_agent"],
    "k8s-only": ["k8s_diagnostic_agent"],
}

ROUTES = {
    "storage-performance": (
        "The store answers HTTP 200 but pages take many seconds. Database pods are running. "
        "Disk write latency on the shared datastore is hundreds of milliseconds, against a normal "
        "read baseline of about 5 to 11 ms. Storage owns this."
    ),
    "database-outage": (
        "The database has no ready replicas, or the store answers HTTP 500 because the database is down. "
        "Do not pick this when the store answers HTTP 200."
    ),
    "cluster-platform": "The Kubernetes cluster or the VCF hosts under it are failing. The database and platform team owns it.",
    "load-balancer": "The Avi load balancer is not passing traffic to healthy members. The load balancer team owns it.",
    "store-application": "The store application itself fails while its database and platform are healthy. The store team owns it.",
    "unknown": "The evidence does not point at one layer. On-call keeps investigating.",
}
ROUTE_TICKET = {
    "storage-performance": ("3 high", "Storage"),
    "database-outage": ("3 high", "Database and platform"),
    "cluster-platform": ("3 high", "Database and platform"),
    "load-balancer": ("2 normal", "Load balancer"),
    "store-application": ("2 normal", "Store application"),
    "unknown": ("2 normal", "On-call"),
}


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S", time.gmtime()), message, flush=True)


def _json(status: int, body: str) -> dict | list | None:
    if status not in (200, 201):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def read_ticket(ticket_id: int) -> dict:
    status, body = zammad_request("GET", f"/api/v1/tickets/{ticket_id}", None)
    ticket = _json(status, body)
    if not isinstance(ticket, dict):
        raise SystemExit(f"Zammad ticket {ticket_id} read failed HTTP {status}")
    status, body = zammad_request("GET", f"/api/v1/ticket_articles/by_ticket/{ticket_id}", None)
    articles = _json(status, body) or []
    text = "\n".join(
        f"{a.get('subject') or ''}: {re.sub(r'<[^>]+>', ' ', a.get('body') or '')}".strip()
        for a in articles
        if isinstance(a, dict)
    )
    return {"id": ticket_id, "number": str(ticket.get("number")), "title": ticket.get("title") or "", "text": text[:3000]}


def jev_choice(state: str, instructions: str, criteria: dict) -> dict:
    row = jev_ask("incident-response-agent", state, {"type": "choice", "instructions": instructions, "criteria": criteria})
    answer = (((row.get("response") or {}).get("answers") or {}).get("q") or {})
    raw = answer.get("probabilities") if isinstance(answer.get("probabilities"), dict) else {}
    probabilities = {
        str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    return {
        "choice": answer.get("choice") if answer.get("choice") in criteria else None,
        "confidence": answer.get("confidence"),
        "probabilities": probabilities,
        "error": row.get("error"),
    }


def agent_prompt(agent: str, ticket: dict, retry_errors: list[str] | None = None) -> str:
    text = (
        f"Incident {ticket['number']}: {ticket['title']}.\n"
        f"Ticket text: {ticket['text'][:1200]}\n\n"
        f"Run your skill `{agent}` now, every step in order. "
        f"incident_id is \"{ticket['number']}\". "
        "If a tool returns an error or a refusal, do not call that tool again in this run: "
        "put it in tools_denied and go on to the next step. "
        "Reply with the findings JSON object only."
    )
    if agent == "vcf_diagnostic_agent":
        text += (
            " The store's worker VMs are: " + ", ".join(topology.store_vms(topology.load())) + "."
            " Call vcf_vm_disk_latency once, with vms set to those names."
            " If the result includes finding, quote that sentence."
            " Do not call vcf_vm_disk_latency again."
            " Do not call vcf_inventory, vcf_list_vms, vcf_list_datastores, or vcf_list_alerts."
            " If that one call times out or errors, put vcf_vm_disk_latency in tools_denied and finish."
        )
    elif agent == "k8s_diagnostic_agent":
        text += (
            " The ticket is slowness, not an outage. Pods may be Running and deployments ready."
            " Read the postgres log and quote a duration of 1000 ms or more if it is there."
            " Do not say the database was scaled to zero unless replicas is 0."
        )
    elif agent == "lb_diagnostic_agent":
        text += (
            " Call avi_latency once with no name. If the result includes finding,"
            " quote that sentence, virtual_services_up, and pools_up. Do not invent a latency number."
            " If the call times out or errors, put avi_latency in tools_denied and finish."
            " Do not call it again."
        )
    if retry_errors:
        text += (
            "\n\nA first attempt was rejected for these reasons: "
            + "; ".join(retry_errors[:6])
            + ". Run the steps again and return a JSON object that fixes them. "
            "Do not write any analysis before or after it; the JSON object is the whole reply."
        )
    return text


# One try each. A hung door used to burn 600s, three times, and the chat
# died before the report. The load balancer and VCF doors now answer inside
# a short read; these waits are the backstop so the note still gets written.
# Captain 2026-10-14: goad-qwen is best-effort-xlarge, 4 vCPU / 32 GiB.
# Expect about 20 to 40 minutes for one enrichment. Each model call may
# take several minutes. 900s is the per-call ceiling, not the expected time.
_AGENT_LIMITS = {
    "lb_diagnostic_agent": (900.0, 1),
    "k8s_diagnostic_agent": (900.0, 1),
    "vcf_diagnostic_agent": (900.0, 1),
}


def run_agent(agent: str, ticket: dict) -> dict:
    app = AGENT_APPS[agent]
    timeout, tries = _AGENT_LIMITS.get(agent, (120.0, 1))
    attempts = []
    errors: list[str] | None = None
    for _ in range(tries):
        log(f"{agent}: asking {app}")
        result = tanzu_agents.ask(app, agent_prompt(agent, ticket, errors), timeout=timeout)
        called = set(tanzu_agents.allowed(result))
        report, errors = (None, [f"chat failed: {result['error']}"]) if result["error"] else validate(
            result["text"], agent=agent, called=called
        )
        attempts.append(
            {
                "ms": result["ms"],
                "calls": result["calls"],
                "stats": result["stats"],
                "errors": errors,
                "reply_chars": len(result["text"]),
            }
        )
        log(f"{agent}: {len(result['calls'])} tool calls, {result['ms']} ms, {'valid' if report else 'rejected: ' + '; '.join(errors[:3])}")
        if report:
            return {"agent": agent, "report": report, "attempts": attempts, "last": result}
    return {"agent": agent, "report": None, "attempts": attempts, "last": result}


def evidence_text(run: dict) -> str:
    agent = run["agent"]
    report: Findings | None = run["report"]
    lines = [f"{DOMAIN_NAME[agent]} ({agent})"]
    if report is None:
        lines.append("  Report rejected, not used as evidence: " + "; ".join(run["attempts"][-1]["errors"][:4]))
        return "\n".join(lines)
    lines.append(f"  Status: {report.status}. Checked at {report.checked_at.isoformat()}.")
    for finding in report.findings:
        raw = json.dumps(finding.evidence.raw_value, ensure_ascii=False)
        if len(raw) > 220:
            raw = raw[:217] + "..."
        lines.append(f"  - [{finding.severity}] {finding.component}: {finding.symptom} ({finding.evidence.tool}: {raw})")
    if report.suspected_cause:
        lines.append(f"  Suspected cause: {report.suspected_cause.cause} (confidence {report.suspected_cause.confidence:.2f})")
    return "\n".join(lines)


def access_text(run: dict) -> str:
    agent = run["agent"]
    # Every attempt counts: a refusal in a retried attempt is still a refusal.
    calls = [c for attempt in run["attempts"] for c in attempt["calls"]]
    result = {"calls": [c for c in calls if c["tool"] not in BUILDER_TOOLS]}
    allowed = tanzu_agents.allowed(result)
    refused = tanzu_agents.denied(result)
    broken = [f for f in tanzu_agents.failed(result) if f["tool"] not in {d["tool"] for d in refused}]
    report: Findings | None = run["report"]
    seen = {d["tool"] for d in refused} | {f["tool"] for f in broken}
    named = [t for t in (report.tools_denied if report else []) if t not in seen]
    lines = [f"{agent}:"]
    lines.append("  Allowed: " + (", ".join(allowed) if allowed else "none"))
    denied = [f"{d['tool']} ({_one_line(d['reason'])})" for d in refused] + [
        f"{t} (reported by the agent as missing or refused)" for t in named
    ]
    lines.append("  Denied: " + (", ".join(denied) if denied else "none"))
    if broken:
        lines.append("  Failed (allowed, but the call broke): " + ", ".join(f"{f['tool']} ({_one_line(f['reason'])})" for f in broken))
    return "\n".join(lines)


def _one_line(reason: str) -> str:
    text = " ".join(reason.replace("Fix the errors and try again.", "").split())
    return text[:140]


def write_narrative(ticket: dict, store: dict, runs: list[dict], route: dict, calls: list[dict]) -> dict:
    """Qwen writes the four prose sections as JSON from validated findings only."""
    valid = {r["agent"]: r["report"].model_dump(mode="json") for r in runs if r["report"]}
    packet = json.dumps(
        {
            "ticket": {"number": ticket["number"], "title": ticket["title"]},
            "store_check": store,
            "route": route,
            "validated_findings": valid,
            "not_checked": [r["agent"] for r in runs if not r["report"]],
        },
        ensure_ascii=False,
    )[:9000]
    prompt = (
        "Write step 4 of your skill for this incident. Use only these facts. "
        "If the store answered HTTP 200 slowly and VCF write latency is hundreds of milliseconds, "
        "the root cause is storage latency. Do not say the database is down.\n"
        "Reply with one JSON object and nothing else, with keys: "
        "summary (one line), root_cause (one sentence), confidence (0 to 1), "
        "impact (one or two sentences), next_steps (list of short strings, each naming who acts).\n\n"
        + packet
    )
    # With thinking on, Qwen spent all 1500 tokens thinking and returned no answer.
    text = qwen_call("incident_response_agent", prompt, calls, max_tokens=1500, reasoning_effort="none")
    doc = _narrative_json(text)
    if not doc:
        # The first reply often echoes a findings object. extract_json prefers
        # that object, so the summary was dropped. Ask once more for the note only.
        retry = (
            "Reply with one JSON object and nothing else. Keys: "
            "summary, root_cause, confidence, impact, next_steps. "
            "summary is one line about this incident.\n\n"
            + packet[:4000]
        )
        text = qwen_call("incident_response_agent", retry, calls, max_tokens=800, reasoning_effort="none")
        doc = _narrative_json(text)
    return doc or {}


def _narrative_json(text: str) -> dict:
    """The prose object, not a findings report that happens to be valid JSON."""
    import json

    keys = ("summary", "root_cause", "confidence", "impact", "next_steps")
    decoder = json.JSONDecoder()
    found = None
    index = (text or "").find("{")
    while index != -1:
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict) and all(k in value for k in keys) and str(value.get("summary") or "").strip():
            found = {k: value[k] for k in keys}
        index = text.find("{", end)
    return found or {}


def compose_note(ticket: dict, store: dict, runs: list[dict], picked: dict, route: dict, prose: dict) -> str:
    called = ", ".join(DOMAIN_NAME[r["agent"]] for r in runs)
    parts = []
    if prose:
        try:
            confidence = f"{float(prose['confidence']):.2f}"
        except (TypeError, ValueError):
            confidence = "not given"
        steps = prose["next_steps"] if isinstance(prose["next_steps"], list) else [prose["next_steps"]]
        parts += [
            "SUMMARY\n" + str(prose["summary"]).strip(),
            f"LIKELY ROOT CAUSE (confidence {confidence})\n" + str(prose["root_cause"]).strip(),
        ]
    else:
        parts += [
            "SUMMARY\nQwen did not return the summary. The evidence below is complete.",
            "LIKELY ROOT CAUSE\nNot written. Read the suspected cause in each evidence block.",
        ]
    parts.append(
        "EVIDENCE BY DOMAIN\n"
        f"Store check: {store.get('url')} answered HTTP {store.get('status')} in {store.get('ms')} ms.\n"
        f"Jev chose these agents: {picked.get('choice') or 'none (Jev did not answer)'}"
        + (f" (confidence {picked['confidence']})" if picked.get("confidence") is not None else "")
        + (". Below 0.70, so all three were checked" if picked.get("used") == "all-three" and picked.get("choice") != "all-three" else "")
        + f". Called: {called}.\n\n"
        + "\n\n".join(evidence_text(r) for r in runs)
    )
    if prose:
        parts.append("IMPACT\n" + str(prose["impact"]).strip())
        parts.append("NEXT STEPS\n" + "\n".join(f"{n}. {str(s).strip()}" for n, s in enumerate(steps, 1)))
    else:
        parts.append("IMPACT\nNot written. See the store check above.")
        parts.append("NEXT STEPS\n1. On-call reads the evidence and picks the owner.")
    parts.append(
        f"ROUTE\nJev chose {route.get('choice') or 'unknown'}"
        + (f" (confidence {route['confidence']})" if route.get("confidence") is not None else "")
        + (". Below 0.70, so on-call picks the owner" if route.get("used") != route.get("choice") else "")
        + f". Priority {route['priority']}, group {route['group']}."
    )
    parts.append("ACCESS LOG\n" + "\n".join(access_text(r) for r in runs))
    parts.append("Written by the incident response agent. No change was made. A person approves every fix.")
    return "\n\n".join(parts)


def ensure_group(name: str) -> int | None:
    """Find or create the group, and keep the on-call user able to see it."""
    status, body = zammad_request("GET", "/api/v1/groups", None)
    group_id = next((g.get("id") for g in _json(status, body) or [] if g.get("name") == name), None)
    if group_id is None:
        status, body = zammad_request("POST", "/api/v1/groups", {"name": name, "active": True})
        created = _json(status, body)
        group_id = created.get("id") if isinstance(created, dict) else None
    if group_id is None:
        return None
    me = _json(*zammad_request("GET", "/api/v1/users/me", None)) or {}
    access = dict(me.get("group_ids") or {})
    if me.get("id") and "full" not in (access.get(str(group_id)) or []):
        access[str(group_id)] = ["full"]
        zammad_request("PUT", f"/api/v1/users/{me['id']}", {"group_ids": access})
    return group_id


def post(ticket_id: int, note: str, priority: str, group: str, tags: list[str]) -> dict:
    group_id = ensure_group(group)
    article_status, _ = zammad_request(
        "POST",
        "/api/v1/ticket_articles",
        {
            "ticket_id": ticket_id,
            "subject": "Enrichment",
            "body": note,
            "content_type": "text/plain",
            "type": "note",
            "internal": False,
            "sender": "Agent",
        },
    )
    update = {"priority": priority}
    if group_id:
        update["group_id"] = group_id
    update_status, _ = zammad_request("PUT", f"/api/v1/tickets/{ticket_id}", update)
    tag_status = {
        tag: zammad_request("POST", "/api/v1/tags/add", {"object": "Ticket", "o_id": ticket_id, "item": tag})[0]
        for tag in tags
    }
    return {
        "article_status": article_status,
        "update_status": update_status,
        "group_id": group_id,
        "tag_status": tag_status,
    }


def run(ticket_id: int | None, open_new: bool, title: str = TITLE) -> dict:
    rec = Reasoning()
    try:
        report = _run(rec, ticket_id, open_new, title)
    except BaseException as exc:
        rec.finish("failed", f"{type(exc).__name__}: {str(exc)[:300]}")
        raise
    rec.finish("done", f"Ticket {report['ticket']['number']} routed to {report['jev_route']['group']} "
               f"at priority {report['jev_route']['priority']}. Note HTTP {report['posted']['article_status']}.")
    return report


def _why(agent: str, picked: dict) -> str:
    if picked.get("used") == picked.get("choice"):
        return (f"Jev picked {picked['choice']} with confidence {picked['confidence']}. {AGENT_SETS[picked['choice']]}")
    return (f"Jev's confidence in its pick ({picked.get('choice') or 'no answer'}) was {picked.get('confidence')}, "
            f"below 0.70, so every domain is checked. This agent covers {DOMAIN_NAME[agent]}.")


def _tool_lines(run: dict) -> list[str]:
    lines = []
    for attempt in run.get("attempts") or []:
        for call in attempt.get("calls") or []:
            tool = call.get("tool") or "tool"
            raw_in = json.dumps(call.get("input"), ensure_ascii=False, default=str)
            raw_out = call.get("error") or json.dumps(call.get("output"), ensure_ascii=False, default=str)
            lines.append(f"{tool} args {raw_in[:180]} result {raw_out[:180]}")
    return lines[:12]


def _run(rec: Reasoning, ticket_id: int | None, open_new: bool, title: str, *,
         snapshot: dict | None = None, post_note: bool = True) -> dict:
    load_env()
    topo = topology.load()
    rec.topology(topology.rows(topo))
    rec.step(f"Loaded the static map {topology.MAP_PATH.name}: {len(topo['pods'])} pods on "
             f"{len(topology.store_vms(topo))} VMs, all on datastore {topo['datastore']['name']}.")
    rec.event(f"Topology loaded: {len(topo['pods'])} pods on {len(topology.store_vms(topo))} VMs, "
              f"datastore {topo['datastore']['name']}.")
    rec.component("Incident response agent", "Loaded the store map, then read the incident ticket.")
    if snapshot is not None:
        store = store_status()
        ticket = {
            "id": int(snapshot["id"]),
            "number": str(snapshot.get("number") or snapshot["id"]),
            "title": snapshot.get("title") or title,
            "text": snapshot.get("text") or "",
        }
        ticket_id = ticket["id"]
    else:
        store = store_status()
        if open_new:
            opened = open_ticket(store, title)
            if not opened.get("ticket_id"):
                raise SystemExit(f"could not open a ticket: HTTP {opened.get('status')}")
            ticket_id = int(opened["ticket_id"])
            log(f"opened Zammad ticket id {ticket_id}")
            rec.step(f"Opened Zammad ticket id {ticket_id}, as monitoring would.")
        ticket = read_ticket(int(ticket_id))
    log(f"store HTTP {store.get('status')}")
    rec.saw("store check", f"{store.get('url')} answered HTTP {store.get('status')} in {store.get('ms')} ms.")
    log(f"ticket {ticket['number']}: {ticket['title']}")
    rec.ticket(ticket)
    rec.saw("Zammad ticket", f"{ticket['number']}: {ticket['title']}. {ticket['text'][:200]}")
    rec.event(f"Incident opened: ticket {ticket['number']}, {ticket['title']}. Store HTTP {store.get('status')}.")
    rec.audience(ticket_number=str(ticket["number"]), title=ticket["title"],
                 assessment=f"Ticket {ticket['number']} is open. The store answered HTTP {store.get('status')}.")
    rec.component("Zammad", f"Ticket {ticket['number']} is open: {ticket['title']}.")

    rec.step("Asked Jev which diagnostic agents to call.")
    picked = jev_choice(
        "metal music store incident, choose diagnostic agents",
        "A Zammad ticket reports a problem with the Metal Music Store on the VCF lab Kubernetes cluster. "
        "Choose which diagnostic agents to call. "
        "When the store answers HTTP 200 but catalog or checkout pages take many seconds, "
        "the load balancer sees that high response time, so include the load balancer agent with Kubernetes and VCF. "
        "Ticket: " + ticket["title"] + ". " + ticket["text"][:1500]
        + f" Store check: HTTP {store.get('status')} in {store.get('ms')} ms. Topology: " + topology.text(topo)[:1200],
        AGENT_SETS,
    )
    # A weak pick would leave domains unchecked. Below 0.70, check all three.
    confident = (picked["confidence"] or 0) >= 0.70
    chosen = SET_MEMBERS[picked["choice"]] if picked["choice"] and confident else SET_MEMBERS["all-three"]
    picked["used"] = picked["choice"] if confident else "all-three"
    log(f"Jev agents: {picked['choice']} {picked['confidence']} error={picked['error']}")
    rec.jev("which agents", picked["choice"], picked["used"], picked["probabilities"], picked["error"],
            picked["confidence"])
    probs = ", ".join(f"{name} {score:.2f}" for name, score in
                      sorted((picked.get("probabilities") or {}).items(), key=lambda kv: -kv[1]))
    rule = ("Jev's confidence was at least 0.70, so that pick is the one used."
            if picked.get("used") == picked.get("choice")
            else "Jev's confidence was below 0.70, so all three domain agents are checked.")
    rec.event(f"Jev chose agents: {picked.get('choice')} (confidence {picked.get('confidence')}). {rule} {probs}.")
    rec.component("Jev", f"Agents: pick {picked.get('choice')}, confidence {picked.get('confidence')}. {rule}")
    rec.audience(jev_agents={"choice": picked.get("choice"), "confidence": picked.get("confidence"),
                             "used": picked.get("used"), "probabilities": picked.get("probabilities"),
                             "rule": rule})

    runs = []
    for agent in chosen:
        rec.agent(AGENT_APPS[agent], _why(agent, picked))
        result = run_agent(agent, ticket)
        calls = sum(len(a["calls"]) for a in result["attempts"])
        report = result["report"]
        finding = (report.suspected_cause.cause if report and report.suspected_cause else
                 (f"status {report.status}, {len(report.findings)} findings" if report else
                  "; ".join(result["attempts"][-1]["errors"][:2])))
        rec.agent_done(AGENT_APPS[agent], "findings valid" if report else "findings rejected", calls, finding)
        label = {"k8s_diagnostic_agent": "K8s agent", "vcf_diagnostic_agent": "VCF agent",
                 "lb_diagnostic_agent": "LB agent"}[agent]
        did = finding
        rec.component(label, did)
        rec.event(f"{label}: {calls} tool calls. {did}")
        called = rec.doc["audience"]["agents_called"]
        called.append({"agent": label, "valid": report is not None, "tools": _tool_lines(result), "finding": finding})
        rec.audience(agents_called=called)
        runs.append(result)
    for agent, label in (
        ("k8s_diagnostic_agent", "K8s agent"),
        ("vcf_diagnostic_agent", "VCF agent"),
        ("lb_diagnostic_agent", "LB agent"),
    ):
        if agent not in chosen:
            rec.component(label, "Not called on this run.")

    valid = {r["agent"]: r["report"].model_dump(mode="json") for r in runs if r["report"]}
    rec.step("Asked Jev for the route from the validated findings.")
    route = jev_choice(
        "metal music store incident, choose route",
        "Choose the route for this incident from the validated agent findings. "
        + json.dumps({"store": store, "findings": valid}, ensure_ascii=False)[:3500],
        ROUTES,
    )
    # A weak route pick goes to on-call, who picks the owner.
    sure = (route["confidence"] or 0) >= 0.70
    choice = route["choice"] if route["choice"] and sure else "unknown"
    route["used"] = choice
    route["priority"], route["group"] = ROUTE_TICKET[choice]
    log(f"Jev route: {route['choice']} {route['confidence']} error={route['error']}")
    rec.jev("route", route["choice"], choice, route["probabilities"], route["error"], route["confidence"])
    route_rule = ("The route stands, because confidence is at least 0.70."
                  if route.get("used") == route.get("choice")
                  else "Confidence was below 0.70, so the ticket goes to on-call.")
    rec.event(f"Jev route: {route.get('choice')} (confidence {route.get('confidence')}). {route_rule} "
              f"Priority {route['priority']}, group {route['group']}.")
    rec.component("Jev", rec.doc["components"][1]["did"] + f" Route: {choice}, confidence {route.get('confidence')}. {route_rule}")
    rec.audience(jev_route={"choice": route.get("choice"), "confidence": route.get("confidence"),
                            "used": choice, "priority": route["priority"], "group": route["group"],
                            "probabilities": route.get("probabilities"), "rule": route_rule})

    rec.step("Qwen is writing the summary, root cause, impact, and next steps.")
    qwen_calls: list[dict] = []
    prose = write_narrative(ticket, store, runs, route, qwen_calls)
    note = compose_note(ticket, store, runs, picked, route, prose)
    tags = ["agent-enriched", choice] + [DOMAIN_TAG[a] for a in chosen]
    rec.audience(enrichment=note, assessment=(prose.get("summary") if prose else "") or rec.doc["audience"]["assessment"])
    if post_note:
        posted = post(int(ticket_id), note, route["priority"], route["group"], tags)
        log(f"posted: {posted}")
        rec.step(f"Posted the note (HTTP {posted['article_status']}), priority {route['priority']}, "
                 f"group {route['group']}, tags {', '.join(tags)}.")
        rec.event(f"Enrichment written to Zammad ticket {ticket['number']} (HTTP {posted['article_status']}).")
        rec.component("Zammad", f"Wrote the enrichment on ticket {ticket['number']} (HTTP {posted['article_status']}). "
                      f"Priority {route['priority']}, group {route['group']}.")
    else:
        rec.pending_zammad(int(ticket_id), note, route["priority"], route["group"], tags)
        posted = {"article_status": None, "queued": True}
        rec.step("Enrichment is ready. The helpdesk write is queued for agents-machine.")
        rec.event(f"Enrichment written for ticket {ticket['number']}. Waiting for the helpdesk write.")
        rec.component("Zammad", f"Enrichment for ticket {ticket['number']} is ready and waiting to be written.")
    rec.component("AgentMinder", "This agent has no Kubernetes or VCF grant. It called the domain agents, "
                  "and those agents used their own grants.")
    rec.event("AgentMinder: the incident response agent made no Kubernetes or VCF call.")

    report = {
        "ticket": ticket,
        "store": store,
        "jev_agents": picked,
        "jev_route": route,
        "agents": [
            {
                "agent": r["agent"],
                "valid": r["report"] is not None,
                "attempts": r["attempts"],
                "report": r["report"].model_dump(mode="json") if r["report"] else None,
            }
            for r in runs
        ],
        "qwen": qwen_calls,
        "note": note,
        "posted": posted,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def _backup(ticket: dict) -> bool:
    return "backup" in str(ticket.get("title") or "").lower()


def latest_open_ticket() -> dict:
    """The newest helpdesk ticket that is still open and is not a backup.

    The search index answers a state query with an empty list, so this reads
    the ticket list, the same way reset does.
    """
    load_env()
    states = _json(*zammad_request("GET", "/api/v1/ticket_states", None)) or []
    open_ids = {row.get("id") for row in states if isinstance(row, dict) and row.get("name") in ("new", "open")}
    tickets: list[dict] = []
    status = 0
    for page in range(1, 51):
        status, body = zammad_request("GET", f"/api/v1/tickets?per_page=100&page={page}", None)
        rows = _json(status, body)
        if not isinstance(rows, list):
            break
        tickets.extend(row for row in rows if isinstance(row, dict))
        if len(rows) < 100:
            break
    open_rows = [
        row for row in tickets
        if row.get("state_id") in open_ids and not _backup(row) and row.get("id")
    ]
    open_rows.sort(key=lambda row: int(row.get("id") or 0), reverse=True)
    if not open_rows:
        raise SystemExit(f"no open incident ticket (list HTTP {status})")
    chosen = open_rows[0]
    return read_ticket(int(chosen["id"]))


def run_latest() -> dict:
    ticket = latest_open_ticket()
    log(f"latest open ticket {ticket['number']} id {ticket['id']}")
    return run(int(ticket["id"]), False, ticket["title"] or TITLE)


def run_prepared(snapshot: dict) -> dict:
    """Enrich a ticket copy. The helpdesk write stays queued for agents-machine."""
    rec = Reasoning()
    try:
        report = _run(rec, int(snapshot["id"]), False, snapshot.get("title") or TITLE,
                      snapshot=snapshot, post_note=False)
    except BaseException as exc:
        rec.finish("failed", f"{type(exc).__name__}: {str(exc)[:300]}")
        rec.audience(state="failed", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        raise
    rec.finish("done", f"Ticket {report['ticket']['number']} routed to {report['jev_route']['group']} "
               f"at priority {report['jev_route']['priority']}. Note queued for the helpdesk.")
    rec.audience(state="done")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich one Zammad ticket")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, help="Zammad ticket id (not the number)")
    group.add_argument("--open", action="store_true", help="Open a bare ticket first, as monitoring would")
    group.add_argument("--latest", action="store_true", help="Enrich the latest open incident ticket")
    parser.add_argument("--title", default=TITLE, help="Title of the ticket --open creates")
    args = parser.parse_args()
    report = run_latest() if args.latest else run(args.ticket, args.open, args.title)
    print(report["note"])
    code = report["posted"]["article_status"]
    return 0 if code in (200, 201) else 1


if __name__ == "__main__":
    raise SystemExit(main())
