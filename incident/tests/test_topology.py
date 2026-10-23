import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import topology  # noqa: E402


class TopologyTest(unittest.TestCase):
    def test_map_loads_in_order(self):
        doc = topology.load()
        rows = topology.rows(doc)
        layers = [row["layer"] for row in rows]
        self.assertEqual(layers[0], "store")
        self.assertEqual(layers[-1], "datastore")
        self.assertEqual([row["order"] for row in rows], sorted(row["order"] for row in rows))
        self.assertIn("pod", layers)
        self.assertIn("VM", layers)

    def test_store_vms_carry_store_pods(self):
        doc = topology.load()
        vms = topology.store_vms(doc)
        self.assertEqual(len(vms), 3)
        self.assertNotIn("${K8S_NODE_CP}", vms)

    def test_text_names_the_datastore(self):
        doc = topology.load()
        self.assertIn(doc["datastore"]["name"], topology.text(doc))

    def test_goad_map_names_platforms(self):
        path = Path(__file__).resolve().parents[1] / "topology" / "goad-music.json"
        doc = topology.load(path)
        self.assertEqual(doc["store"]["platform"], "VKS")
        self.assertEqual(doc["store"]["kind"], "app")
        details = " ".join(row["detail"] for row in topology.rows(doc))
        self.assertIn("platform VKS", details)
        self.assertIn("platform VM", details)
        self.assertIn("platform DSM", details)
        self.assertIn("platform VCF", details)
        self.assertIn("kind data", details)


if __name__ == "__main__":
    unittest.main()
