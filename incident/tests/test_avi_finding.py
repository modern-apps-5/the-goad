"""VIP and pool health become one sentence. No controller call."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("avi_server", ROOT / "avi-mcp" / "server.py")
assert spec and spec.loader
avi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(avi)


class HealthFindingTest(unittest.TestCase):
    def test_healthy_only_when_vip_and_pool_are_up(self) -> None:
        vs = {"oper_state": "OPER_UP", "enabled": True, "vip": ["203.0.113.10"]}
        pool = {"name": "store", "oper_state": "OPER_UP", "servers_up": 3, "servers": 3}
        self.assertEqual(avi.health_finding(vs, pool), "LB healthy, no latency anomaly at the VIP")

    def test_down_vip_is_not_called_healthy(self) -> None:
        vs = {"oper_state": "OPER_DOWN", "enabled": True, "vip": ["203.0.113.10"]}
        pool = {"name": "store", "oper_state": "OPER_UP", "servers_up": 3, "servers": 3}
        self.assertIn("OPER_DOWN", avi.health_finding(vs, pool))
        self.assertNotIn("no latency anomaly", avi.health_finding(vs, pool))

    def test_missing_pool_does_not_claim_healthy(self) -> None:
        vs = {"oper_state": "OPER_UP", "enabled": True, "vip": "203.0.113.10"}
        self.assertEqual(avi.health_finding(vs, None), "")

    def test_partial_members(self) -> None:
        vs = {"oper_state": "OPER_UP", "enabled": True}
        pool = {"name": "store", "oper_state": "OPER_UP", "servers_up": 1, "servers": 3}
        self.assertEqual(avi.health_finding(vs, pool), "VIP is OPER_UP but 1 of 3 pool members are up.")


if __name__ == "__main__":
    unittest.main()
