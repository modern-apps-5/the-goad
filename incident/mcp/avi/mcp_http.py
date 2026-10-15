"""Small JSON-RPC MCP over HTTP. No third-party SDK.

Read and write tokens must both be set, and they must differ.
This server does not log Authorization headers.

Behind the AgentMinder AI Gateway the caller presents an AgentMinder
access token instead of a static token. `idsp_bearer` (copied from the
company Kubernetes door at push time) checks the signature, issuer, and
audience. Such a caller only ever gets read access, and only the tools
its grant names.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


class Tool:
    def __init__(self, name: str, description: str, schema: dict, fn: ToolFn, *, read_only: bool):
        self.name = name
        self.description = description
        self.schema = schema
        self.fn = fn
        self.read_only = read_only

    def list_item(self) -> dict:
        return {"name": self.name, "description": self.description, "inputSchema": self.schema}


def _idsp():
    try:
        import idsp_bearer
    except ImportError:
        return None
    return idsp_bearer


class McpServer:
    def __init__(self, name: str, version: str, read_token: str, write_token: str):
        if not read_token or not write_token:
            raise SystemExit("MCP_READ_TOKEN and MCP_WRITE_TOKEN must be set")
        if read_token == write_token:
            raise SystemExit("MCP_READ_TOKEN and MCP_WRITE_TOKEN must differ")
        self.name = name
        self.version = version
        self.read_token = read_token
        self.write_token = write_token
        self.tools: dict[str, Tool] = {}
        self.health_extra: dict[str, Any] = {}
        self.resource_url = (os.environ.get("MCP_RESOURCE_URL") or "").strip().rstrip("/")

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def protected_resource(self) -> dict:
        issuer = (os.environ.get("IDSP_ISSUER") or "https://${AGENTMINDER_HOST}/default").rstrip("/")
        return {
            "resource": self.resource_url,
            "authorization_servers": [issuer],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [t.name for t in self.tools.values() if t.read_only],
            "resource_name": self.name,
        }

    @staticmethod
    def _bearer(header: str | None) -> str:
        if not header or not header.lower().startswith("bearer "):
            return ""
        return header.split(" ", 1)[1].strip()

    def role_for(self, header: str | None) -> str | None:
        token = self._bearer(header)
        if not token:
            return None
        if token == self.write_token:
            return "write"
        if token == self.read_token:
            return "read"
        ib = _idsp()
        if ib is None or not self.resource_url:
            return None
        capability = ib.classify_idsp(
            token,
            default_resource=self.resource_url,
            read_scopes=[t.name for t in self.tools.values() if t.read_only],
        )
        return "read" if capability else None

    def granted_tools(self, header: str | None) -> set[str] | None:
        """Tool names an AgentMinder token names, or None when the grant is an intent or the token is static."""
        token = self._bearer(header)
        if not token or token in (self.read_token, self.write_token):
            return None
        ib = _idsp()
        claims = ib.verify_idsp_jwt(token) if ib else None
        if not claims:
            return None
        scopes = set((claims.get("scope") or "").split())
        named = {t for t in self.tools if t in scopes}
        if not named and ib.intent_grant(claims):
            # The gateway in front maps the intent to tools and strips the rest.
            return None
        return named

    def handle(self, body: dict, role: str, granted: set[str] | None = None) -> dict:
        req_id = body.get("id")
        method = body.get("method") or ""
        params = body.get("params") or {}
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }
        if method in ("notifications/initialized", "notifications/cancelled", "ping"):
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "tools/list":
            tools = [
                t.list_item()
                for t in self.tools.values()
                if (role == "write" or t.read_only) and (granted is None or t.name in granted)
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        if method == "tools/call":
            name = params.get("name") or ""
            args = params.get("arguments") or {}
            tool = self.tools.get(name)
            if tool is None:
                return _err(req_id, -32601, f"unknown tool {name}")
            if granted is not None and name not in granted:
                return _err(req_id, -32603, f"intent denied: {name} is not in this grant")
            if role == "read" and not tool.read_only:
                return _err(req_id, -32603, f"intent denied: {name} needs write access")
            try:
                result = tool.fn(args if isinstance(args, dict) else {})
            except Exception as exc:
                return _err(req_id, -32603, str(exc)[:400])
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }
        return _err(req_id, -32601, f"unknown method {method}")


def _err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve(server: McpServer, host: str, port: int) -> None:
    mcp = server

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _json(self, code: int, payload: dict | list) -> None:
            raw = json.dumps(payload).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/mcp":
                # No server-initiated stream. A 404 here reads as a dead session.
                self.send_response(405)
                self.send_header("Allow", "POST")
                self.end_headers()
                return
            if path in ("/health", "/"):
                body = {"ok": True, "server": mcp.name}
                body.update(mcp.health_extra)
                self._json(200, body)
                return
            if path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"):
                self._json(200, mcp.protected_resource())
                return
            self._json(404, {"ok": False})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if path != "/mcp":
                self._json(404, {"ok": False})
                return
            auth = self.headers.get("Authorization")
            role = mcp.role_for(auth)
            if role is None:
                self._json(401, {"error": "unauthorized"})
                return
            granted = mcp.granted_tools(auth)
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode())
            except json.JSONDecodeError:
                self._json(400, {"error": "bad json"})
                return
            if isinstance(body, list):
                self._json(200, [mcp.handle(item, role, granted) for item in body if isinstance(item, dict)])
                return
            self._json(200, mcp.handle(body, role, granted))

    ThreadingHTTPServer((host, port), Handler).serve_forever()
