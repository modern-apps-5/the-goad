#!/usr/bin/env python3
"""Small scrubber. Redacts emails and phone-like numbers. Does not start itself."""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")


def scrub(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    return PHONE.sub("[phone]", text)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/health", "/"):
            self.send_response(404)
            self.end_headers()
            return
        body = b'{"status":"idle"}\n'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/scrub":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            doc = json.loads(raw) if raw else {}
            text = doc.get("text") if isinstance(doc, dict) else raw
        except json.JSONDecodeError:
            text = raw
        body = json.dumps({"text": scrub(str(text or ""))}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
