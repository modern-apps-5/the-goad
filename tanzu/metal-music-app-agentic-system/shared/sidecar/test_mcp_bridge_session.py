"""A dead AgentMinder session is dropped once and the official call is retried."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "site-packages"))
sys.path.insert(0, str(HERE))

import mcp_bridge  # noqa: E402


WRAPPED = {
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32603,
        "message": "MCP tools/call error 2002: AI Gateway: Backend rejected request",
    },
}


class BackendRejected(unittest.TestCase):
    def test_wrapped_2002_is_a_dead_session(self) -> None:
        self.assertTrue(mcp_bridge.backend_session_rejected(WRAPPED))

    def test_no_grant_packet_is_not_a_dead_session(self) -> None:
        doc = {"error": {"code": 2002, "message": "AI Gateway: Backend unavailable"}}
        self.assertFalse(mcp_bridge.backend_session_rejected(doc))
        self.assertTrue(mcp_bridge.gateway_denied(doc))

    def test_delegate_drops_the_session_and_retries_once(self) -> None:
        import asyncio

        calls = {"n": 0}
        dropped = {"n": 0}

        async def official(scope, receive, send):
            calls["n"] += 1
            while True:
                msg = await receive()
                if msg["type"] != "http.request":
                    break
                if not msg.get("more_body"):
                    break
            if calls["n"] == 1:
                payload = WRAPPED
            else:
                payload = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True, "replay": True}}
            data = json.dumps(payload).encode()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": data})

        def drop() -> None:
            dropped["n"] += 1

        real_app = mcp_bridge._official_app
        real_drop = mcp_bridge.drop_pooled_sessions
        mcp_bridge._official_app = official
        mcp_bridge.drop_pooled_sessions = drop
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "vcf_vm_disk_latency", "arguments": {}}}
        ).encode()
        try:
            asyncio.run(
                mcp_bridge._delegate(
                    {"type": "http", "query_string": b""},
                    body,
                    send,
                    1,
                    tool="vcf_vm_disk_latency",
                    rpc_method="tools/call",
                )
            )
        finally:
            mcp_bridge._official_app = real_app
            mcp_bridge.drop_pooled_sessions = real_drop

        self.assertEqual(calls["n"], 2)
        self.assertEqual(dropped["n"], 1)
        raw = b"".join(msg.get("body", b"") for msg in sent if msg.get("type") == "http.response.body")
        self.assertIn(b'"replay": true', raw)
        self.assertNotIn(b"Backend rejected", raw)


if __name__ == "__main__":
    unittest.main()
