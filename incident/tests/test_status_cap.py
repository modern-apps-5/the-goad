"""The incident chat must stop polling before the model window fills."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import orchestrator.incident_live as live


class StatusCapTest(unittest.TestCase):
    def test_status_stops_after_six_calls(self) -> None:
        live._POLLS = 0
        live._RUNNING = True
        live._STATUS_WAIT = 0
        try:
            with patch.object(live, "_compact", side_effect=lambda **kwargs: {"state": "running", "stop": kwargs["stop"]}):
                seen = [live._status() for _ in range(8)]
        finally:
            live._STATUS_WAIT = 25
            live._RUNNING = False
            live._POLLS = 0
        self.assertFalse(seen[0]["stop"])
        self.assertTrue(seen[5]["stop"])
        self.assertEqual(seen[5]["state"], "done")
        self.assertTrue(seen[7]["stop"])


if __name__ == "__main__":
    unittest.main()
