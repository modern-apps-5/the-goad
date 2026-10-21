"""MCP protocol bridge in front of the official AgentMinder sidecar app.

**This is not a gateway bypass.** It holds no AgentMinder credentials
and never calls the AI Gateway. ``tools/call`` is delegated unchanged
to ``agentminder.sidecar:app``, which mints the agent token and
forwards to the gateway. Grant and revoke keep working on the wire
because this file cannot run a tool without the official app.

Every bind passes the gateway's own ``tools/list`` through. That list is
grant-filtered, so an agent sees only the tools AgentMinder granted it.

Why it exists: the official sidecar implements exactly three JSON-RPC
methods and answers **400** to anything else (see `_json(send, 400,
{"error": f"unsupported MCP method ..."})`). Tanzu Agent Builder is a
spec-compliant MCP client, so straight after `initialize` it posts the
`notifications/initialized` notification. The 400 kills the client's
writer task and every agent turn fails afterwards.

This bridge answers the transport-level obligations the official app
skips, and nothing else:

* a notification (JSON-RPC message with no ``id``) gets 202 and no body
* `GET /mcp` gets 405 when there is no server-initiated SSE stream
* `DELETE /mcp` (session teardown) gets 204
* an unsupported method stops being an HTTP 400 and becomes a normal
  JSON-RPC ``-32601 method not found`` at HTTP 200, which is what a
  JSON-RPC server owes a client. The gateway advertises `prompts` and
  `resources` capabilities that the sidecar cannot serve, so a client is
  entitled to ask for them; it must not lose its connection for asking.

No successful tool result is invented here. ``tools/call`` still goes
through the official app. If that app returns AI Gateway ``2002
Backend unavailable`` on ``initialize`` or ``tools/list`` — this nest
will not open the VCF backend without a grant — the bridge keeps the
official app in the chain. ``initialize`` gets a handshake so the bind
stays up. ``tools/list`` is an empty list, because nothing is granted. On a 2002 call error, the bridge may append what the
official sidecar already decoded on this agent's token (whether any
``vcf_`` scopes are present). If that cached token has no ``vcf_``
scopes, the official SDK will keep it until it expires — about an
hour on this nest, so a 90 second grant wait is not enough. The
bridge then asks the official client to mint again and retries the
same official call once. It does not guess. A later grant still
goes through the official app.

A different 2002, ``Backend rejected request``, means the pooled MCP
session is dead (the door restarted, or the gateway dropped it) while
the tool list is still cached. The official app wraps that as
``MCP tools/call error 2002``. The bridge drops the pooled session and
retries the same official call once. The retry opens a new session.
A second rejection is returned as-is.

Captain 2026-08-28 allowed an undocumented path provided the sidecar
stays in the request chain and nothing bypasses the gateway.

  uvicorn departments.it.mcp.sidecar.mcp_bridge:app --host 127.0.0.1 --port 8181
"""

from __future__ import annotations

import json
from typing import Any

from agentminder import sidecar as official
from agentminder.client import AgentMinderClient

# The official sidecar mints a client-credentials token with no scope.
# IDSP then returns only urn:iam:m.meclient, the Kubernetes door answers
# 401, and the gateway reports 2002. Requesting urn:iam:myscopes is how
# this product puts the Grant's tool names on the token. The sidecar
# has no environment key for that scope, so set it on the agent the
# sidecar builds. The official app still mints the token and still
# forwards the call.
_orig_agent = AgentMinderClient.agent


def _agent_requests_myscopes(self, client_id, **kwargs):
    kwargs.setdefault("default_scopes", ("urn:iam:myscopes",))
    return _orig_agent(self, client_id, **kwargs)


AgentMinderClient.agent = _agent_requests_myscopes

try:  # Optional. Absent or unconfigured, the bridge behaves exactly as before.
    import access_emit as _access
except ImportError:  # pragma: no cover — droplet without the emitter
    _access = None

# Delegate target. Keep the official module object so a vendor upgrade is
# picked up without touching this file.
_official_app = official.app

MCP_PATH = "/mcp"
_DISCOVERY = frozenset({"initialize", "tools/list"})

# How much of an answer we copy to classify allow vs deny. A refusal is short;
# a real tool result can be large and is none of the access log's business.
_PEEK = 4096


def gateway_denied(doc: object) -> bool:
    """True when the AI Gateway used 2002 instead of an empty tools list."""
    if not isinstance(doc, dict):
        return False
    err = doc.get("error")
    if not isinstance(err, dict):
        return False
    msg = str(err.get("message") or "")
    if err.get("code") == 2002:
        return True
    return "Backend unavailable" in msg or "MCP initialize error 2002" in msg


def backend_session_rejected(doc: object) -> bool:
    """True when a tool call died because the pooled gateway session is dead.

    The official sidecar wraps the gateway packet as
    ``MCP tools/call error 2002: AI Gateway: Backend rejected request``
    with JSON-RPC code -32603. A fresh session still succeeds. This is
    not the no-grant ``Backend unavailable`` packet.
    """
    if not isinstance(doc, dict):
        return False
    err = doc.get("error")
    if not isinstance(err, dict):
        return False
    msg = str(err.get("message") or "")
    if "Backend rejected" not in msg:
        return False
    return err.get("code") == 2002 or "2002" in msg


def drop_pooled_sessions() -> None:
    """Close the official sidecar's MCP sessions so the next call opens one."""
    client = getattr(official.state, "client", None)
    pool = getattr(client, "_pool", None) if client is not None else None
    clear = getattr(pool, "clear", None)
    if not callable(clear):
        return
    try:
        clear()
    except Exception:
        return


def lifespan_denied(reason: str) -> bool:
    """Official prewarm died on this nest's no-grant 2002."""
    return "2002" in reason or "Backend unavailable" in reason


def vcf_scopes_from_claims(claims: object) -> list[str] | None:
    """VCF grant on a decoded token, or None if there is no token.

    Counts legacy tool-name scopes (``vcf_*``) and AgentMinder job
    scopes (``urn:iam:agent:intent:*``). A token that carries a job
    is granted; saying it has "no VCF scopes" was wrong (2026-09-20).
    """
    if not isinstance(claims, dict):
        return None
    raw = claims.get("scope")
    if raw is None:
        raw = claims.get("scp")
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        scopes = [str(s) for s in raw]
    else:
        scopes = str(raw).split()
    return [
        s
        for s in scopes
        if s.startswith("vcf_") or s.startswith("urn:iam:agent:intent:")
    ]


def _jwt_claims(token: str) -> dict | None:
    """Decode a JWT payload. No verify. Never log the token."""
    import base64

    parts = token.split(".")
    if len(parts) < 2:
        return None
    pad = "=" * (-len(parts[1]) % 4)
    try:
        doc = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
    except Exception:
        return None
    return doc if isinstance(doc, dict) else None


def official_vcf_scopes() -> list[str] | None:
    """Read VCF scopes from the official sidecar's already-minted agent token.

    Does not mint, does not call the gateway. None means we cannot see a
    token, so do not guess why the call failed.
    """
    try:
        client = official.state.client
        agent = official.state.agent
    except Exception:
        return None
    if client is None:
        return None
    cid = getattr(agent, "client_id", None) if agent is not None else None
    if not cid:
        return None
    claims = None
    if hasattr(client, "last_token_claims_for"):
        try:
            claims = client.last_token_claims_for(cid)
        except Exception:
            claims = None
    if claims is None:
        identity = getattr(client, "_identity", None)
        cache = getattr(identity, "_token_cache", None) if identity is not None else None
        entries = getattr(cache, "_entries", None) if cache is not None else None
        if isinstance(entries, dict):
            for key, tok in entries.items():
                if not isinstance(key, tuple) or key[0] != cid:
                    continue
                raw = getattr(tok, "access_token", "") or ""
                claims = _jwt_claims(raw)
                if claims is not None:
                    break
    return vcf_scopes_from_claims(claims)


def should_refresh_stale_token(vcf_scopes: list[str] | None, retried: bool) -> bool:
    """True when the cached token is the reason 2002 can linger after a grant."""
    return (not retried) and vcf_scopes is not None and len(vcf_scopes) == 0


def refresh_official_agent_token() -> list[str] | None:
    """Force-mint a new official agent token. Does not call the AI Gateway."""
    try:
        client = official.state.client
        agent = official.state.agent
        resources = getattr(official.state, "resources", None) or {}
        name = getattr(official.state, "default_resource", None)
        res = resources.get(name) if name else None
        if res is None and isinstance(resources, dict) and resources:
            res = next(iter(resources.values()))
        if client is None or agent is None or res is None:
            return None
        pool = getattr(client, "_pool", None)
        if pool is not None and hasattr(pool, "clear"):
            try:
                pool.clear()
            except Exception:
                pass
        client.authenticate_agent(agent, resource=res, force=True)
    except Exception:
        return None
    return official_vcf_scopes()


def annotate_call_error(doc: object, vcf_scopes: list[str] | None) -> dict[str, Any]:
    """Keep the official 2002 words. Add the token fact when we can see it."""
    if not isinstance(doc, dict):
        return {"jsonrpc": "2.0", "error": {"code": -32603, "message": "invalid tool result"}}
    if not gateway_denied(doc):
        return doc
    if vcf_scopes is None:
        return doc
    err = doc.get("error")
    if not isinstance(err, dict):
        return doc
    msg = str(err.get("message") or "").strip()
    if vcf_scopes:
        return doc
    extra = (
        "This agent's token has no VCF scopes. "
        "AgentMinder has not granted them."
    )
    if extra in msg:
        return doc
    out = dict(doc)
    out["error"] = dict(err)
    out["error"]["message"] = f"{msg} {extra}".strip()
    return out


def discovery_failed(doc: object, status: int) -> bool:
    """Discovery should stay up, not kill the Agent Builder session."""
    if status != 200:
        return True
    if gateway_denied(doc):
        return True
    return isinstance(doc, dict) and "error" in doc


def discovery_shape(method: str, rpc_id: Any) -> dict[str, Any]:
    """Keep the bind up when the gateway will not open the backend."""
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentminder-sidecar", "version": "0.2.0"},
            },
        }
    if method == "tools/list":
        # A refused door has no granted tools. Say so with an empty list.
        return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": []}}
    raise ValueError("discovery_shape is only for initialize and tools/list")


async def _lifespan(scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Keep the process up when official prewarm dies on gateway 2002.

    ``_bootstrap`` already stored client, agent, and resources before
    ``prewarm``. A later grant still uses that official client.
    """

    async def _send(msg: dict[str, Any]) -> None:
        if msg.get("type") == "lifespan.startup.failed":
            reason = str(msg.get("message") or "")
            if lifespan_denied(reason):
                return await send({"type": "lifespan.startup.complete"})
        return await send(msg)

    await _official_app(scope, receive, _send)


async def _read_body(receive: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        msg = await receive()
        if msg["type"] != "http.request":
            break
        chunks.append(msg.get("body", b""))
        if not msg.get("more_body"):
            break
    return b"".join(chunks)


def _replay(body: bytes) -> Any:
    """Hand the already-consumed body to the official app."""
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


async def _empty(send: Any, status: int) -> None:
    await send({"type": "http.response.start", "status": status, "headers": []})
    await send({"type": "http.response.body", "body": b""})


async def _json_response(send: Any, status: int, body: Any) -> None:
    data = json.dumps(body).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(data)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": data})


async def _delegate(
    scope: dict[str, Any],
    body: bytes,
    send: Any,
    rpc_id: Any,
    *,
    tool: str = "",
    rpc_method: str = "",
    retried: bool = False,
) -> None:
    """Run the official app, turning its 400 into a JSON-RPC error.

    Only a 400 is ever buffered; every other response streams straight
    through so tool results are untouched.

    When ``tool`` is set and an access log is configured, the first few KB of
    the answer are copied as they stream past so the gateway's decision can be
    recorded. The copy is bounded and the response is never delayed by it.
    """
    rewrite = rpc_method in _DISCOVERY
    rewrite_call = rpc_method == "tools/call"
    held: dict[str, Any] = {"headers": None, "buffering": False, "start": None}
    chunks = bytearray()
    watch = bool(tool) and _access is not None and _access.enabled()
    seen = bytearray()
    status_seen: dict[str, int] = {"code": 0}
    stale: dict[str, Any] = {"doc": None}
    rejected: dict[str, bool] = {"hit": False}

    def _record() -> None:
        if not watch:
            return
        try:
            _access.send(
                _access.build_row(
                    tool=tool,
                    door=_access.door_from_query(scope.get("query_string", b"")),
                    status=status_seen["code"],
                    body=bytes(seen),
                )
            )
        except Exception:
            return

    async def _send(msg: dict[str, Any]) -> None:
        if msg["type"] == "http.response.start":
            status_seen["code"] = int(msg.get("status") or 0)
            if rewrite or rewrite_call or msg.get("status") == 400:
                held["buffering"] = True
                held["headers"] = msg.get("headers") or []
                held["start"] = msg
                return
            return await send(msg)
        if msg["type"] == "http.response.body" and not held["buffering"]:
            if watch and len(seen) < _PEEK:
                seen.extend(msg.get("body", b"")[: _PEEK - len(seen)])
            out = await send(msg)
            if not msg.get("more_body"):
                _record()
            return out
        if msg["type"] == "http.response.body" and held["buffering"]:
            chunks.extend(msg.get("body", b""))
            if msg.get("more_body"):
                return
            raw = bytes(chunks)
            if watch:
                seen.extend(raw[:_PEEK])
                _record()
            if rewrite or rewrite_call:
                try:
                    doc = json.loads(raw.decode() or "{}")
                except json.JSONDecodeError:
                    doc = {}
                if rewrite and discovery_failed(doc, status_seen["code"]):
                    return await _json_response(
                        send, 200, discovery_shape(rpc_method, rpc_id)
                    )
                if rewrite_call and backend_session_rejected(doc) and not retried:
                    rejected["hit"] = True
                    return
                if rewrite_call and gateway_denied(doc):
                    scopes = official_vcf_scopes()
                    if should_refresh_stale_token(scopes, retried):
                        stale["doc"] = doc
                        return
                    return await _json_response(
                        send, 200, annotate_call_error(doc, scopes)
                    )
                start = held.get("start") or {
                    "type": "http.response.start",
                    "status": status_seen["code"] or 200,
                    "headers": held["headers"] or [],
                }
                await send(start)
                return await send({"type": "http.response.body", "body": raw})
            if b"unsupported MCP method" in raw:
                method = ""
                try:
                    method = str(json.loads(raw).get("error") or "")
                except json.JSONDecodeError:
                    pass
                return await _json_response(
                    send,
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32601,
                            "message": method or "method not found",
                        },
                    },
                )
            await send({"type": "http.response.start", "status": 400, "headers": held["headers"]})
            return await send({"type": "http.response.body", "body": raw})
        return await send(msg)

    await _official_app(scope, _replay(body), _send)
    if rejected["hit"]:
        drop_pooled_sessions()
        return await _delegate(
            scope,
            body,
            send,
            rpc_id,
            tool=tool,
            rpc_method=rpc_method,
            retried=True,
        )
    if stale["doc"] is not None:
        new_scopes = refresh_official_agent_token()
        if new_scopes:
            return await _delegate(
                scope,
                body,
                send,
                rpc_id,
                tool=tool,
                rpc_method=rpc_method,
                retried=True,
            )
        return await _json_response(
            send, 200, annotate_call_error(stale["doc"], official_vcf_scopes())
        )


def _is_notification(payload: Any) -> bool:
    """JSON-RPC notification: a request object carrying no ``id``."""
    if isinstance(payload, dict):
        return "method" in payload and "id" not in payload
    if isinstance(payload, list) and payload:
        return all(isinstance(m, dict) and "method" in m and "id" not in m for m in payload)
    return False


async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    if scope["type"] == "lifespan":
        return await _lifespan(scope, receive, send)
    if scope["type"] != "http":
        return await _official_app(scope, receive, send)

    path = scope.get("path", "")
    method = scope.get("method", "")

    # No server-initiated SSE stream here. The spec answer is 405, not the
    # official app's 401/404, which some clients treat as a hard failure.
    if path == MCP_PATH and method == "GET":
        return await _empty(send, 405)

    # Session teardown. Nothing to tear down locally; the official app
    # pools its own gateway session and closes it on lifespan shutdown.
    if path == MCP_PATH and method == "DELETE":
        return await _empty(send, 204)

    if path != MCP_PATH or method != "POST":
        return await _official_app(scope, receive, send)

    body = await _read_body(receive)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        return await _official_app(scope, _replay(body), send)

    if not _is_notification(payload):
        rpc_id = payload.get("id") if isinstance(payload, dict) else None
        tool = ""
        if _access is not None:
            try:
                tool = _access.tool_name(payload)
            except Exception:
                tool = ""
        rpc_method = ""
        if isinstance(payload, dict):
            rpc_method = str(payload.get("method") or "")
        return await _delegate(
            scope, body, send, rpc_id, tool=tool, rpc_method=rpc_method
        )

    # Same local-token rule the official app applies to every /mcp call.
    if not official._authorized(scope):  # noqa: SLF001 — vendor's own check
        return await _json_response(send, 401, {"error": "unauthorized"})
    return await _empty(send, 202)
