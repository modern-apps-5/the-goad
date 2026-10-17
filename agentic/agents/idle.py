#!/usr/bin/env python3
"""Idle HTTP server for an agent process.

Serves /health. Does not call the model, Zammad, or the MCP servers.
demo.sh start does not talk to this process.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/health", "/"):
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps(
            {"status": "idle", "name": os.environ.get("AGENT_NAME", "agent")}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
