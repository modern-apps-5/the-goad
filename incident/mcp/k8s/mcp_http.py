"""Minimal JSON-RPC MCP over HTTP. No third-party MCP SDK.

Bearer roles:
  write token → all tools
  read token  → tools flagged read_only
  missing/wrong → 401

Never log Authorization headers or token values.
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
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.schema,
        }


def _env_token(name: str) -> str:
    return (os.environ.get(name) or "").strip()


class McpServer:
    def __init__(self, name: str, version: str = "0.1.0"):
        self.name = name
        self.version = version
        self.tools: dict[str, Tool] = {}
        self.health_extra: dict[str, Any] = {}
        self.resource_url = _env_token("MCP_RESOURCE_URL")
        self.read_token = _env_token("MCP_READ_TOKEN")
        self.write_token = _env_token("MCP_WRITE_TOKEN")
        self.on_denied: Callable[[str, str], None] | None = None
        self.on_call: Callable[[str, str, bool], None] | None = None
        self.ingest_watch_event: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        self.forward_tap: Callable[..., tuple[int, bytes, str]] | None = None
        self.render_watch: Callable[[], dict[str, Any]] | None = None
        self.render_desk: Callable[[], dict[str, Any]] | None = None
        self.render_chat: Callable[[], dict[str, Any]] | None = None
        self.handle_chat: Callable[[dict[str, Any]], dict[str, Any]] | None = None
        if not self.read_token or not self.write_token:
            raise SystemExit("MCP_READ_TOKEN and MCP_WRITE_TOKEN must be set")
        if self.read_token == self.write_token:
            raise SystemExit("MCP_READ_TOKEN and MCP_WRITE_TOKEN must differ")

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def protected_resource(self) -> dict[str, Any]:
        """RFC 9728 metadata so AgentMinder can onboard this MCP."""
        url = self.resource_url or f"https://{self.name}.${TANZU_APPS_DOMAIN}/mcp"
        issuer = (_env_token("IDSP_ISSUER") or "https://${AGENTMINDER_HOST}/default").rstrip("/")
        scopes = [t.name for t in self.tools.values()]
        return {
            "resource": url,
            "authorization_servers": [issuer],
            "bearer_methods_supported": ["header"],
            "scopes_supported": scopes,
            "resource_name": self.name,
        }

    def read_scope_names(self) -> list[str]:
        return [t.name for t in self.tools.values() if t.read_only]

    def write_scope_names(self) -> list[str]:
        return [t.name for t in self.tools.values() if not t.read_only]

    def role_for(self, auth_header: str | None) -> str | None:
        """Static lab tokens for ops; IDSP JWT for Grant on the wire.

        Sidecar Mode presents an agent access token whose scopes are the
        Grant's tool names, with ``aud`` the AI Gateway route. Anything the
        Grant does not name maps to no role at all.
        """
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        if token and token == self.write_token:
            return "write"
        if token and token == self.read_token:
            return "read"
        if not token:
            return None
        try:
            import idsp_bearer as ib
        except ImportError:
            return None
        default_resource = self.resource_url or f"https://{self.name}.${TANZU_APPS_DOMAIN}/mcp"
        capability = ib.classify_idsp(
            token,
            default_resource=default_resource,
            read_scopes=self.read_scope_names(),
            write_scopes=self.write_scope_names(),
        )
        # classify_idsp speaks 'admin'; this server speaks 'write'.
        return "write" if capability == "admin" else capability

    def granted_tools(self, auth_header: str | None) -> set[str] | None:
        """Tool names named by an IDSP token, or None for a static token.

        The Grant is per tool, so a coarse read/write role is not enough:
        `memory-mcp-desk` and `memory-mcp-read` are both "some of memory-mcp".
        Static ops tokens keep the old role behaviour.
        """
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        if not token or token in (self.read_token, self.write_token):
            return None
        try:
            import idsp_bearer as ib
        except ImportError:
            return None
        claims = ib.verify_idsp_jwt(token)
        if not claims:
            return None
        scopes = set((claims.get("scope") or "").split())
        named = {t for t in self.tools if t in scopes}
        if not named and getattr(ib, "intent_grant", None) and ib.intent_grant(claims):
            # Job on the token, no tool names. The AI Gateway maps the
            # job to tools and strips the rest; this door serves the
            # catalog and lets the role decide read vs write.
            return None
        return named or set()

    def tools_for(self, role: str, granted: set[str] | None = None) -> list[Tool]:
        if granted is not None:
            return [t for t in self.tools.values() if t.name in granted]
        if role == "write":
            return list(self.tools.values())
        return [t for t in self.tools.values() if t.read_only]

    def handle_rpc(self, body: dict, role: str, granted: set[str] | None = None) -> dict:
        req_id = body.get("id")
        method = body.get("method") or ""
        params = body.get("params") or {}
        if method in ("initialize",):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }
        if method in ("notifications/initialized", "notifications/cancelled"):
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "tools/list":
            tools = [t.list_item() for t in self.tools_for(role, granted)]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        if method == "tools/call":
            name = (params.get("name") if isinstance(params, dict) else None) or ""
            args = (params.get("arguments") if isinstance(params, dict) else None) or {}
            tool = self.tools.get(name)
            if not tool:
                return _err(req_id, -32601, f"unknown tool {name}")
            if granted is not None and name not in granted:
                if self.on_denied:
                    try:
                        self.on_denied(name, role)
                    except Exception:
                        pass
                self._emit_call(name, role, False)
                return _err(req_id, -32603, f"intent denied: {name} is not in this Grant")
            if granted is None and role == "read" and not tool.read_only:
                if self.on_denied:
                    try:
                        self.on_denied(name, role)
                    except Exception:
                        pass
                self._emit_call(name, role, False)
                return _err(req_id, -32603, f"intent denied: {name} needs write access")
            try:
                result = tool.fn(args if isinstance(args, dict) else {})
            except Exception as e:
                self._emit_call(name, role, False)
                return _err(req_id, -32603, str(e)[:400])
            self._emit_call(name, role, True)
            text = json.dumps(result, indent=2)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": text}]},
            }
        return _err(req_id, -32601, f"unknown method {method}")

    def _emit_call(self, name: str, role: str, ok: bool) -> None:
        if self.on_call:
            try:
                self.on_call(name, role, ok)
                return
            except Exception:
                return
        try:
            from watch_events import emit_remote

            emit_remote(self.name, role, name, ok)
        except Exception:
            return


def _err(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def make_handler(server: McpServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            msg = fmt % args
            if "authorization" in msg.lower() or "bearer" in msg.lower():
                return
            super().log_message("%s", msg.split("Authorization")[0][:200])

        def _send(
            self,
            code: int,
            payload: dict | None = None,
            raw: bytes | None = None,
            content_type: str = "application/json",
        ) -> None:
            body = raw if raw is not None else json.dumps(payload or {}).encode()
            try:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Agent Builder probes and drops. A short write must not
                # take a worker thread down or stall Diego's /health.
                return

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/mcp":
                # No server-initiated SSE stream. Spec answer is 405.
                # A 404 here makes Agent Builder treat the session as dead.
                try:
                    self.send_response(405)
                    self.send_header("Allow", "POST")
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return
                return
            if path in ("/health", "/"):
                payload = {"ok": True, "server": server.name}
                extra = getattr(server, "health_extra", None) or {}
                if isinstance(extra, dict):
                    payload.update(extra)
                self._send(200, payload)
                return
            if path in (
                "/.well-known/oauth-protected-resource",
                "/.well-known/oauth-protected-resource/mcp",
            ):
                self._send(200, server.protected_resource())
                return
            if path in ("/tap/vcf", "/tap/tanzu"):
                tap = getattr(server, "forward_tap", None)
                if tap is None:
                    self._send(404, {"error": "not found"})
                    return
                kind = "vcf" if path.endswith("/vcf") else "tanzu"
                query = self.path.split("?", 1)[1] if "?" in self.path else ""
                try:
                    status, out, ctype = tap(kind, b"", dict(self.headers), method="GET", query=query)
                except TypeError:
                    try:
                        status, out, ctype = tap(kind, b"", dict(self.headers))
                    except Exception:
                        self._send(502, {"error": "tap failed"})
                        return
                except Exception:
                    self._send(502, {"error": "tap failed"})
                    return
                self._send(
                    status,
                    raw=out if isinstance(out, bytes) else json.dumps(out).encode(),
                    content_type=ctype or "application/json",
                )
                return
            if path in ("/watch", "/observe", "/watch.json"):
                render = getattr(server, "render_watch", None)
                if render is None:
                    self._send(404, {"error": "not found"})
                    return
                try:
                    doc = render()
                except Exception:
                    self._send(500, {"error": "watch failed"})
                    return
                if path == "/watch.json":
                    self._send(200, doc.get("json") or {})
                    return
                html = str(doc.get("html") or "")
                self._send(200, raw=html.encode(), content_type="text/html; charset=utf-8")
                return
            if path in ("/desk", "/desk.json"):
                render = getattr(server, "render_desk", None)
                if render is None:
                    self._send(404, {"error": "not found"})
                    return
                try:
                    doc = render()
                except Exception:
                    self._send(500, {"error": "desk failed"})
                    return
                if path == "/desk.json":
                    self._send(200, doc.get("json") or {})
                    return
                html = str(doc.get("html") or "")
                self._send(200, raw=html.encode(), content_type="text/html; charset=utf-8")
                return
            if path in ("/chat", "/chat/", "/chat.json"):
                render = getattr(server, "render_chat", None)
                if render is None:
                    self._send(404, {"error": "not found"})
                    return
                try:
                    doc = render()
                except Exception:
                    self._send(500, {"error": "chat failed"})
                    return
                if path == "/chat.json":
                    self._send(200, doc.get("json") or {})
                    return
                html = str(doc.get("html") or "")
                self._send(200, raw=html.encode(), content_type="text/html; charset=utf-8")
                return
            self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"

            if path in ("/tap/vcf", "/tap/tanzu"):
                tap = getattr(server, "forward_tap", None)
                if tap is None:
                    self._send(404, {"error": "not found"})
                    return
                kind = "vcf" if path.endswith("/vcf") else "tanzu"
                query = self.path.split("?", 1)[1] if "?" in self.path else ""
                try:
                    status, out, ctype = tap(kind, raw, dict(self.headers), method="POST", query=query)
                except TypeError:
                    try:
                        status, out, ctype = tap(kind, raw, dict(self.headers))
                    except Exception:
                        self._send(502, {"error": "tap failed"})
                        return
                except Exception:
                    self._send(502, {"error": "tap failed"})
                    return
                self._send(
                    status,
                    raw=out if isinstance(out, bytes) else json.dumps(out).encode(),
                    content_type=ctype or "application/json",
                )
                return

            try:
                body = json.loads(raw.decode() or "{}")
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid json"})
                return

            # Public stage chat API — no bearer; tools still enforced per persona matrix + MCP tokens server-side
            if path == "/chat/api":
                handler = getattr(server, "handle_chat", None)
                if handler is None:
                    self._send(404, {"error": "not found"})
                    return
                if not isinstance(body, dict):
                    self._send(400, {"error": "invalid json"})
                    return
                try:
                    out = handler(body)
                except Exception as e:
                    self._send(500, {"error": str(e)[:200]})
                    return
                self._send(200, out if isinstance(out, dict) else {"ok": False})
                return

            if path == "/access":
                ingest = getattr(server, "ingest_access", None)
                if ingest is None:
                    self._send(404, {"error": "not found"})
                    return
                if not isinstance(body, dict):
                    self._send(400, {"error": "invalid json"})
                    return
                try:
                    out = ingest(body)
                except Exception:
                    self._send(500, {"error": "access ingest failed"})
                    return
                self._send(200 if out.get("ok") else 400, out)
                return

            if path == "/watch/event":
                ingest = getattr(server, "ingest_watch_event", None)
                if ingest is None:
                    self._send(404, {"error": "not found"})
                    return
                if not isinstance(body, dict):
                    self._send(400, {"error": "invalid json"})
                    return
                try:
                    out = ingest(body)
                except Exception:
                    self._send(500, {"error": "watch event failed"})
                    return
                code = 200 if out.get("ok") else 400
                self._send(code, out)
                return

            if path not in ("/mcp", "/"):
                self._send(404, {"error": "not found"})
                return
            auth = self.headers.get("Authorization")
            role = server.role_for(auth)
            if role is None:
                self._send(401, {"error": "unauthorized"})
                return
            granted = server.granted_tools(auth)
            if isinstance(body, list):
                out = [
                    server.handle_rpc(item, role, granted)
                    for item in body
                    if isinstance(item, dict)
                ]
                self._send(200, raw=json.dumps(out).encode())
                return
            if not isinstance(body, dict):
                self._send(400, {"error": "invalid json"})
                return
            self._send(200, server.handle_rpc(body, role, granted))

    return Handler


def serve(server: McpServer, host: str = "0.0.0.0", port: int = 8080) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(server))
    httpd.serve_forever()
