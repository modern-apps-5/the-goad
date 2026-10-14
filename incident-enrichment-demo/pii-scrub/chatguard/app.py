#!/usr/bin/env python3
"""Chat guard for the incident agent's on-stage contact beat.

Cloud Foundry sends POST /api/chat on the incident host here.
A message that contains an email, phone, card, or SSN is answered
in this process: the fixed guardrail line, then the masked complaint.
The model is not called. Every other request is streamed to the
origin route, which is the same agent on a second hostname.

Do not log bodies.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT))

from guardrail import compose  # noqa: E402
from scrub import apply_mask  # noqa: E402

OWN_HOSTS = frozenset({"pii-chat-guard.${TANZU_APPS_DOMAIN}", "localhost", "127.0.0.1"})
MAX_BODY = 2_000_000
_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
        "host",
        "accept-encoding",
    }
)
_PASS = (
    "content-type",
    "cache-control",
    "x-accel-buffering",
    "x-vercel-ai-ui-message-stream",
)


def read_body(handler: BaseHTTPRequestHandler) -> bytes:
    te = (handler.headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in te:
        chunks: list[bytes] = []
        while True:
            line = handler.rfile.readline()
            if not line:
                break
            size_token = line.strip().split(b";", 1)[0] or b"0"
            size = int(size_token, 16)
            if size == 0:
                handler.rfile.readline()
                break
            chunks.append(handler.rfile.read(size))
            handler.rfile.read(2)
        return b"".join(chunks)
    raw_len = handler.headers.get("Content-Length")
    if raw_len is None or raw_len == "":
        return b""
    length = int(raw_len)
    if length > MAX_BODY:
        raise ValueError("body too large")
    return handler.rfile.read(length) if length else b""


def last_user_text(body: dict[str, Any]) -> str:
    found = ""
    for message in body.get("messages") or []:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        found = _flatten_message(message)
    return found


def _flatten_message(message: dict[str, Any]) -> str:
    parts: list[str] = []
    content = message.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if isinstance(text, str):
                    parts.append(text)
    for part in message.get("parts") or []:
        if isinstance(part, dict) and part.get("type") in (None, "text"):
            text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(part for part in parts if part)


def line_for(body: dict[str, Any]) -> str | None:
    """The guardrail line when this turn contains contact details.

    Contact details win even if the same message also says the ticket
    phrase. A real enrich request has no email, phone, card, or SSN,
    so it returns None and is passed through.
    """
    text = last_user_text(body).strip()
    if not text:
        return None
    return compose(apply_mask(text))


def sse_events(line: str) -> bytes:
    text_id = str(uuid.uuid4())
    events: list[dict[str, Any]] = [
        {"type": "start"},
        {"type": "start-step"},
        {"type": "text-start", "id": text_id},
        {"type": "text-delta", "id": text_id, "delta": line},
        {"type": "text-end", "id": text_id},
        {"type": "finish-step"},
        {"type": "finish", "finishReason": "stop"},
    ]
    chunks = [f"data: {json.dumps(event)}\n\n" for event in events]
    chunks.append("data: [DONE]\n\n")
    return "".join(chunks).encode("utf-8")


def ssl_context() -> ssl.SSLContext:
    candidates = [
        os.environ.get("SSL_CERT_FILE") or "",
        str(ROOT / "ca.pem"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


def _host(handler: BaseHTTPRequestHandler) -> str:
    return (handler.headers.get("Host") or "").split(":")[0].lower()


def _own(handler: BaseHTTPRequestHandler) -> bool:
    return _host(handler) in OWN_HOSTS and not handler.headers.get("X-CF-Forwarded-Url")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        code = args[1] if len(args) > 1 else ""
        sys.stderr.write("%s %s %s\n" % (self.command, self.path.split("?", 1)[0], code))

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _is_chat(self) -> bool:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        return path == "/api/chat"

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        # Diego's health check uses the container address as Host.
        # Answer here unless a route service forwarded the call.
        if not self.headers.get("X-CF-Forwarded-Url") and path in ("/health", "/"):
            self._send(200, {"status": "ok", "role": "chat-guard"})
            return
        if _own(self) and path == "/ready":
            self._ready()
            return
        self._proxy(None)

    def do_POST(self) -> None:  # noqa: N802
        try:
            raw = read_body(self)
        except ValueError:
            self._send(400, {"error": "bad body"})
            return
        if self._is_chat():
            line = _line_from(raw)
            if line:
                sys.stderr.write("guard-chat line bytes=%s\n" % len(raw))
                self._sse(line)
                return
        sys.stderr.write("guard-chat proxy bytes=%s\n" % len(raw))
        self._proxy(raw)

    def _ready(self) -> None:
        target = os.environ.get("CHAT_ORIGIN", "").rstrip("/")
        if not target:
            self._send(503, {"origin": "unset"})
            return
        url = target + "/health"
        try:
            kwargs: dict[str, Any] = {"timeout": 10}
            if url.startswith("https"):
                kwargs["context"] = ssl_context()
            with urlopen(Request(url, method="GET"), **kwargs) as resp:
                code = resp.status
        except Exception as exc:
            sys.stderr.write("guard-ready %s\n" % type(exc).__name__)
            self._send(503, {"origin": type(exc).__name__})
            return
        self._send(200 if code == 200 else 503, {"origin": "ok" if code == 200 else "http"})

    def _sse(self, line: str) -> None:
        raw = sse_events(line)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("X-Vercel-Ai-Ui-Message-Stream", "v1")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()

    def _target(self) -> str:
        forwarded = self.headers.get("X-CF-Forwarded-Url")
        if forwarded:
            return forwarded
        base = os.environ.get("CHAT_ORIGIN", "").rstrip("/")
        if not base:
            return ""
        return base + self.path

    def _proxy(self, raw: bytes | None) -> None:
        target = self._target()
        forwarded = self.headers.get("X-CF-Forwarded-Url")
        if not target:
            self._send(502, {"error": "origin-unset"})
            return
        if not forwarded and (self.headers.get("Host") or "").lower() == urlparse(target).netloc.lower():
            self._send(502, {"error": "origin-loop"})
            return
        method = self.command
        data = None if method in ("GET", "HEAD") else (raw or b"")
        headers = {}
        for key, value in self.headers.items():
            if key.lower() in _HOP:
                continue
            if key.lower().startswith("x-cf-") and not forwarded:
                continue
            headers[key] = value
        headers["Accept-Encoding"] = "identity"
        req = Request(target, data=data, method=method, headers=headers)
        timeout = float(os.environ.get("CHAT_PROXY_TIMEOUT", "600"))
        kwargs: dict[str, Any] = {"timeout": timeout}
        if target.startswith("https"):
            kwargs["context"] = ssl_context()
        try:
            resp = urlopen(req, **kwargs)
        except HTTPError as exc:
            resp = exc
        except (URLError, TimeoutError, OSError) as exc:
            sys.stderr.write("guard-chat origin %s\n" % type(exc).__name__)
            self._send(502, {"error": "origin-unavailable"})
            return
        try:
            self.protocol_version = "HTTP/1.0"
            self.close_connection = True
            self.send_response(resp.status)
            for key in _PASS:
                value = resp.headers.get(key)
                if value:
                    self.send_header(key, value)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
        finally:
            resp.close()


def _line_from(raw: bytes) -> str | None:
    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    try:
        return line_for(body)
    except Exception as exc:
        sys.stderr.write("guard-chat mask-failed %s\n" % type(exc).__name__)
        return None


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    bind_port = int(os.environ.get("PORT") or port or 8080)
    httpd = ThreadingHTTPServer((host, bind_port), Handler)
    sys.stderr.write("pii-chat-guard listening on %s:%s\n" % (host, bind_port))
    httpd.serve_forever()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
