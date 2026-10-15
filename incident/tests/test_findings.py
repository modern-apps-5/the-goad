"""The Pydantic models match skills/schema/findings.schema.json.

    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import get_args

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.findings import (  # noqa: E402
    SCHEMA_PATH,
    Finding,
    Findings,
    SuspectedCause,
    extract_json,
    validate,
)

GOOD = {
    "agent": "k8s_diagnostic_agent",
    "incident_id": "34010",
    "checked_at": "2026-10-12T16:00:00Z",
    "status": "failed",
    "findings": [
        {
            "component": "deployment/postgres",
            "symptom": "Scaled to 0 replicas",
            "evidence": {"tool": "k8s_list_deployments", "raw_value": {"name": "postgres", "replicas": 0}},
            "severity": "critical",
        }
    ],
    "suspected_cause": {"cause": "The database deployment has no pods", "confidence": 0.9},
    "recommended_action": "Scale postgres back to 1 after on-call approves.",
    "tools_used": ["k8s_list_deployments"],
    "tools_denied": [],
}


class SchemaMatchesModels(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_required_fields(self) -> None:
        self.assertEqual(set(self.schema["required"]), set(Findings.model_json_schema()["required"]))
        item = self.schema["properties"]["findings"]["items"]
        self.assertEqual(set(item["required"]), set(Finding.model_json_schema()["required"]))
        cause = self.schema["properties"]["suspected_cause"]
        self.assertEqual(set(cause["required"]), set(SuspectedCause.model_json_schema()["required"]))

    def test_enums(self) -> None:
        props = self.schema["properties"]
        self.assertEqual(set(props["agent"]["enum"]), set(get_args(Findings.model_fields["agent"].annotation)))
        self.assertEqual(set(props["status"]["enum"]), set(get_args(Findings.model_fields["status"].annotation)))
        severity = props["findings"]["items"]["properties"]["severity"]["enum"]
        self.assertEqual(set(severity), set(get_args(Finding.model_fields["severity"].annotation)))


class Validate(unittest.TestCase):
    def test_good_report_in_fenced_reply(self) -> None:
        text = "Done.\n```json\n" + json.dumps(GOOD) + "\n```"
        report, errors = validate(text, agent="k8s_diagnostic_agent", called={"k8s_list_deployments"})
        self.assertEqual(errors, [])
        self.assertEqual(report.status, "failed")

    def test_prefixed_tool_name_matches_the_call(self) -> None:
        prefixed = json.loads(json.dumps(GOOD))
        prefixed["findings"][0]["evidence"]["tool"] = "sc-k8s-diagnostic-agent-k8s_k8s_list_deployments"
        prefixed["tools_used"] = ["sc-k8s-diagnostic-agent-k8s_k8s_list_deployments"]
        report, errors = validate(
            json.dumps(prefixed),
            agent="k8s_diagnostic_agent",
            called={"k8s_list_deployments"},
        )
        self.assertEqual(errors, [])
        self.assertIsNotNone(report)

    def test_claim_without_a_call_is_rejected(self) -> None:
        report, errors = validate(json.dumps(GOOD), agent="k8s_diagnostic_agent", called=set())
        self.assertIsNone(report)
        self.assertTrue(any("was not called" in e for e in errors))

    def test_schema_violation_is_rejected(self) -> None:
        bad = {**GOOD, "status": "broken"}
        report, errors = validate(json.dumps(bad), agent="k8s_diagnostic_agent", called={"k8s_list_deployments"})
        self.assertIsNone(report)
        self.assertTrue(any(e.startswith("status") for e in errors))

    def test_extra_field_is_rejected(self) -> None:
        bad = {**GOOD, "guess": "maybe"}
        report, _errors = validate(json.dumps(bad), agent="k8s_diagnostic_agent", called={"k8s_list_deployments"})
        self.assertIsNone(report)

    def test_extract_takes_the_last_object(self) -> None:
        self.assertEqual(extract_json('{"a": 1} then {"b": 2}'), {"b": 2})

    def test_every_skill_names_every_required_key(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for agent in ("lb_diagnostic_agent", "k8s_diagnostic_agent", "vcf_diagnostic_agent"):
            text = (ROOT / "skills" / agent / "SKILL.md").read_text(encoding="utf-8")
            output = text.split("## Output", 1)[1]
            for key in schema["required"]:
                self.assertIn(f"`{key}`", output, f"{agent} output section does not name {key}")

    def test_cut_off_reply_is_rejected(self) -> None:
        text = 'Step 1 {"component": "vs", "symptom": "up"} then {"agent": "lb_diagnostic_agent", "findings": ['
        report, errors = validate(text, agent="lb_diagnostic_agent", called=set())
        self.assertIsNone(report)
        self.assertIn("ended before", errors[0])


if __name__ == "__main__":
    unittest.main()
