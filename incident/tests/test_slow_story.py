"""The presenter start does not copy a ticket, and restore undoes the delay."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SlowStoryTest(unittest.TestCase):
    def test_start_does_not_copy_the_ticket(self):
        text = (ROOT / "orchestrator" / "demo_start.py").read_text(encoding="utf-8")
        self.assertNotIn("_publish", text)
        self.assertNotIn("incident-snapshot", text)
        self.assertIn("Metal Music Store slow", (ROOT / "orchestrator" / "incident_title.py").read_text(encoding="utf-8"))

    def test_inject_does_not_scale_postgres_to_zero(self):
        text = (ROOT / "fault-injection" / "fault.py").read_text(encoding="utf-8")
        self.assertNotIn("scale(0)", text)
        sql = (ROOT / "fault-injection" / "storage_load.py").read_text(encoding="utf-8")
        self.assertIn("pg_sleep(10)", sql)
        self.assertIn("DROP VIEW IF EXISTS albums", sql)

    def test_route_is_storage(self):
        text = (ROOT / "orchestrator" / "enrich.py").read_text(encoding="utf-8")
        self.assertIn('"storage-performance"', text)
        self.assertIn('"Storage"', text)

    def test_slow_store_includes_the_load_balancer(self):
        text = (ROOT / "orchestrator" / "enrich.py").read_text(encoding="utf-8")
        self.assertIn("high response time on the load balancer", text)
        self.assertIn("Do not pick this when the store answers HTTP 200 and pages are slow.", text)
        topo = (ROOT / "orchestrator" / "topology.py").read_text(encoding="utf-8")
        self.assertIn("Avi load balancer", topo)


if __name__ == "__main__":
    unittest.main()
