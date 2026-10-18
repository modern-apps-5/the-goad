#!/usr/bin/env python3
"""Plain HTTP door in front of the Goad model ingress.

The agent checks the certificate name. This container cannot edit
/etc/hosts, and the certificate name is not the ingress address.
The agent talks to 127.0.0.1. This process opens TLS to the ingress
with the certificate name and the CA shipped beside this file.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LISTEN = ("127.0.0.1", 8765)
UPSTREAM = "10.47.7.73"
SNI = "pais-ingress-default"
CA = Path(__file__).resolve().parent / "pais-root.pem"


def opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context(cafile=str(CA))

    class Handler(urllib.request.HTTPSHandler):
        def https_open(self, request):
            def mk(host, timeout=None, source_address=None):
                class Conn(urllib.request.http.client.HTTPSConnection):
                    def connect(self):
                        sock = socket.create_connection((UPSTREAM, 443), self.timeout)
                        self.sock = ctx.wrap_socket(sock, server_hostname=SNI)

                return Conn(host, timeout=timeout, context=ctx)

            return self.do_open(mk, request)

    return urllib.request.build_opener(Handler())


OPENER = opener()


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._forward()

    def do_POST(self):
        self._forward()

    def log_message(self, fmt, *args):
        return

    def _forward(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(f"https://{SNI}{self.path}", data=body, method=self.command)
        for key, value in self.headers.items():
            if key.lower() in ("host", "content-length", "transfer-encoding", "connection"):
                continue
            req.add_header(key, value)
        try:
            with OPENER.open(req, timeout=120) as resp:
                payload = resp.read()
                status = resp.status
                headers = list(resp.headers.items())
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            status = exc.code
            headers = list(exc.headers.items()) if exc.headers else []
        except Exception:
            payload = b"model proxy failed"
            status = 502
            headers = []
        self.send_response(status)
        for key, value in headers:
            if key.lower() in ("transfer-encoding", "connection", "content-length", "content-encoding"):
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    try:
        server = ThreadingHTTPServer(LISTEN, Proxy)
    except OSError as exc:
        if getattr(exc, "errno", None) == 98:
            return
        raise
    print("model proxy listening", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
