#!/usr/bin/env python3
"""Incident response chat.

Zammad and the decision gate only. Diagnostic tools stay on the other
agents. The orchestrator runs those agents. This process posts the note.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TRIGGER = "pick up the latest incident ticket"

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Incident response</title>
<style>
  body { font-family: sans-serif; margin: 2rem; max-width: 48rem; }
  pre { white-space: pre-wrap; background: #f4f4f4; padding: 1rem; min-height: 8rem; }
  button { margin-top: 0.5rem; }
</style>
</head>
<body>
<h1>Incident response</h1>
<p>Ask the agent to pick up the latest incident ticket and enrich it.</p>
<form id="talk">
  <input id="msg" size="70" value="pick up the latest incident ticket and enrich it">
  <button type="submit">Send</button>
</form>
<pre id="out"></pre>
<script>
document.getElementById("talk").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const out = document.getElementById("out");
  out.textContent = "";
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message: document.getElementById("msg").value})
  });
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const step = await reader.read();
    if (step.done) break;
    buf += dec.decode(step.value, {stream: true});
    const parts = buf.split("\\n\\n");
    buf = parts.pop();
    for (const part of parts) {
      const line = part.split("\\n").find((row) => row.startsWith("data:"));
      if (!line) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") continue;
      try {
        const obj = JSON.parse(data);
        if (obj.delta) out.textContent += obj.delta;
      } catch (err) {}
    }
  }
});
</script>
</body>
</html>
"""


def _open(req: urllib.request.Request, timeout: int, connect_ip: str = ""):
    """Open a URL. connect_ip dials that address and keeps the original Host."""
    ctx = ssl._create_unverified_context()
    parsed = urllib.parse.urlparse(req.full_url)
    if connect_ip and parsed.hostname:
        netloc = connect_ip if not parsed.port else f"{connect_ip}:{parsed.port}"
        req.full_url = urllib.parse.urlunparse(parsed._replace(netloc=netloc))
        req.add_header("Host", parsed.hostname)
    if req.full_url.startswith("https://"):
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)


def zammad(method: str, path: str, payload: dict | None = None) -> tuple[int, str]:
    root = os.environ.get("ZAMMAD_URL", "").rstrip("/")
    token = os.environ.get("ZAMMAD_TOKEN", "")
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        root + path,
        data=data,
        method=method,
        headers={"Authorization": f"Token token={token}", "Content-Type": "application/json"},
    )
    try:
        with _open(req, 20, os.environ.get("ZAMMAD_CONNECT_IP", "").strip()) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def latest_ticket() -> dict:
    # Search stays empty while Elasticsearch is off, so the ticket list
    # is the source. Newest created_at is the open incident.
    status, body = zammad("GET", "/api/v1/tickets", None)
    rows = json.loads(body) if status == 200 else []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"no open ticket (HTTP {status})")
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    ticket = rows[0]
    tid = ticket.get("id")
    status, body = zammad("GET", f"/api/v1/ticket_articles/by_ticket/{tid}", None)
    articles = json.loads(body) if status == 200 else []
    text = " ".join((a.get("body") or "") for a in articles if isinstance(a, dict))
    return {
        "id": tid,
        "number": str(ticket.get("number") or tid),
        "title": ticket.get("title") or "",
        "text": text[:2000],
    }


def post_note(ticket_id: int, note: str) -> int:
    status, _body = zammad(
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
    return status


def orchestrate(ticket: dict):
    url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8080/run")
    req = urllib.request.Request(
        url,
        data=json.dumps(ticket).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with _open(req, 700, os.environ.get("ORCHESTRATOR_CONNECT_IP", "").strip()) as resp:
        for line in resp:
            line = line.strip()
            if line:
                yield json.loads(line.decode())


def sse(obj) -> bytes:
    return f"data: {json.dumps(obj)}\n\n".encode()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/":
            body = _PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/health":
            body = json.dumps({"ok": True, "agent": "incident-response-agent"}).encode()
        elif path == "/live":
            try:
                with urllib.request.urlopen("http://orchestrator:8080/live", timeout=5) as resp:
                    body = resp.read()
            except Exception:
                body = b'{"steps":[]}\n'
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
        if self.path.split("?", 1)[0] != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        try:
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
        message = str(payload.get("message") or "")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def emit(obj) -> None:
            self._chunk(sse(obj))

        if TRIGGER not in message.lower():
            emit({"delta": "Say: pick up the latest incident ticket and enrich it."})
            emit("[DONE]")
            self._chunk(b"")
            return
        try:
            ticket = latest_ticket()
        except Exception as exc:
            emit({"delta": f"Could not read Zammad ({type(exc).__name__})."})
            emit("[DONE]")
            self._chunk(b"")
            return
        emit({"delta": f"Ticket {ticket['number']}: {ticket['title']}\n"})
        note = ""
        fallback = True
        try:
            for event in orchestrate(ticket):
                if event.get("step"):
                    emit({"delta": event["step"] + "\n"})
                if event.get("note"):
                    note = event["note"]
                    fallback = bool(event.get("fallback"))
        except Exception as exc:
            emit({"delta": f"Orchestrator stalled ({type(exc).__name__}). Posting what we have.\n"})
            note = note or f"Decision gate: CLM fallback (CLM_URL is unset).\nOrchestrator did not finish: {type(exc).__name__}."
        if not note:
            note = "Decision gate: CLM fallback (CLM_URL is unset).\nNo diagnostic result came back."
        status = post_note(int(ticket["id"]), note)
        emit({"delta": f"\nPosted the enrichment to Zammad ticket {ticket['number']} (HTTP {status}).\n"})
        if fallback:
            emit({"delta": "Decision gate is on fallback. CLM_URL is unset.\n"})
        emit({"delta": "\n" + note})
        emit("[DONE]")
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
