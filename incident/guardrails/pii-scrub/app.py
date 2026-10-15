#!/usr/bin/env python3
"""AI Services tile chat webhook — Presidio PII scrub.

Tile 10.4.3 (ai-server 0.81.0) POSTs OpenAI JSON to:

  POST {chat_base_url}/prompt           ChatCompletionRequest
  POST {chat_base_url}/response         ChatCompletion
  POST {chat_base_url}/response/stream  ChatCompletionChunk

Return the same object with PII replaced. 404 on unused paths is
skipped by the tile (NotFound). Other 4xx/5xx fail the chat request.
Do not log bodies.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guardrail import apply_response, observe_prompt, status  # noqa: E402
from scrub import Scrubber  # noqa: E402

CHAT_PATHS = ("/prompt", "/response", "/response/stream")

# Tests assign this. Production main() loads Presidio once.
SCRUBBER: Scrubber | None = None
ENGINE_NAME = "presidio"


def get_scrubber() -> Scrubber:
    global SCRUBBER
    if SCRUBBER is None:
        SCRUBBER = Scrubber()
    return SCRUBBER


def health_body() -> dict[str, Any]:
    return {"status": "ok", "engine": ENGINE_NAME}


def read_body(handler: BaseHTTPRequestHandler) -> bytes:
    """Read JSON body. Tile Java client may send chunked encoding."""
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
        return b"{}"
    length = int(raw_len)
    return handler.rfile.read(length) if length else b"{}"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?", 1)[0]))

    def _send(self, code: int, payload: dict[str, Any] | list[Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/health", "/"):
            self._send(200, health_body())
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path not in CHAT_PATHS:
            self.send_error(404, "Not Found")
            return
        try:
            raw = read_body(self)
        except ValueError:
            self._send(400, {"error": "bad content-length"})
            return
        te = (self.headers.get("Transfer-Encoding") or "-").split(",")[0]
        cl = self.headers.get("Content-Length") or "-"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            sys.stderr.write(
                "POST %s in=%s cl=%s te=%s invalid-json\n" % (path, len(raw), cl, te)
            )
            self._send(400, {"error": "invalid json"})
            return
        if not isinstance(body, (dict, list)):
            self._send(400, {"error": "json object required"})
            return
        try:
            cleaned = get_scrubber().obj(body)
        except Exception as exc:
            sys.stderr.write("scrub-failed %s %s\n" % (path, type(exc).__name__))
            self._send(500, {"error": "scrub-failed"})
            return
        # Qwen thinking-only replies leave the agent history ending on the
        # model response, and the next step raises "must end with a
        # ModelRequest". This endpoint honors reasoning_effort and ignores
        # enable_thinking. The agent binary cannot send the switch. LB and
        # K8s use this same door.
        if path == "/prompt" and isinstance(cleaned, dict):
            observe_prompt(cleaned)
            sys.stderr.write("guard-prompt %s\n" % status())
            if not cleaned.get("reasoning_effort"):
                cleaned["reasoning_effort"] = "none"
                sys.stderr.write("prompt-extra reasoning_effort=none\n")
        elif path in ("/response", "/response/stream"):
            apply_response(cleaned)
            sys.stderr.write("guard-response %s\n" % status())
        out = json.dumps(cleaned).encode("utf-8")
        sys.stderr.write(
            "POST %s in=%s out=%s cl=%s te=%s\n" % (path, len(raw), len(out), cl, te)
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    bind_port = int(os.environ.get("PORT") or port or 8080)
    httpd = ThreadingHTTPServer((host, bind_port), Handler)
    sys.stderr.write("pii-scrub listening on %s:%s\n" % (host, bind_port))
    httpd.serve_forever()


def main() -> None:
    global SCRUBBER
    SCRUBBER = Scrubber()
    serve()


if __name__ == "__main__":
    main()
