"""Pydantic models for skills/schema/findings.schema.json.

The Tanzu agents return text, so the harness validates each report here.
tests/test_findings.py keeps these models and the JSON schema in step.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "skills" / "schema" / "findings.schema.json"

AgentName = Literal["lb_diagnostic_agent", "k8s_diagnostic_agent", "vcf_diagnostic_agent"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_Strict):
    tool: str = Field(min_length=1)
    raw_value: Any


class Finding(_Strict):
    component: str = Field(min_length=1)
    symptom: str = Field(min_length=1)
    evidence: Evidence
    severity: Literal["info", "warning", "critical"]


class SuspectedCause(_Strict):
    cause: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Findings(_Strict):
    agent: AgentName
    incident_id: str = Field(min_length=1)
    checked_at: datetime
    status: Literal["healthy", "degraded", "failed"]
    findings: list[Finding]
    suspected_cause: SuspectedCause | None
    recommended_action: str
    tools_used: list[str]
    tools_denied: list[str]


def extract_json(text: str) -> dict | None:
    """The last JSON object in an agent reply, fenced or bare."""
    decoder = json.JSONDecoder()
    found = None
    report = None
    index = text.find("{")
    while index != -1:
        try:
            value, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index = text.find("{", index + 1)
            continue
        if isinstance(value, dict):
            found = value
            if "agent" in value:
                report = value
        index = text.find("{", end)
    # A reply cut off mid-report still holds whole inner objects (one
    # finding, one evidence block). Those are not the report.
    return report if report is not None else found


def _bare_tool(name: str) -> str:
    """The playbook name, without the AgentMinder door prefix.

    The stream records `sc-k8s-diagnostic-agent-k8s_k8s_list_pods`. The
    skill tells the model to write `k8s_list_pods`. Both name the same call.
    """
    text = name.strip()
    for door in ("k8s", "vcf", "avi"):
        marker = f"-{door}_"
        idx = text.rfind(marker)
        if idx != -1:
            text = text[idx + len(marker):]
            break
    for door in ("k8s_", "vcf_", "avi_"):
        doubled = door + door
        if text.startswith(doubled):
            text = text[len(door):]
            break
    return text


def _tool_was_called(name: str, called: set[str]) -> bool:
    bare = _bare_tool(name)
    return any(_bare_tool(item) == bare for item in called)


def validate(text: str, *, agent: str, called: set[str]) -> tuple[Findings | None, list[str]]:
    """Return the report and an empty list, or None and the reasons it was rejected.

    A report is rejected when it does not match the schema, names another
    agent, or cites a tool this agent did not call in this run.
    """
    doc = extract_json(text)
    if doc is None:
        return None, ["no JSON object in the reply"]
    if "agent" not in doc:
        return None, ["the reply ended before the findings JSON object was complete"]
    try:
        report = Findings.model_validate(doc)
    except ValidationError as exc:
        return None, [
            f"{'.'.join(str(p) for p in err['loc']) or 'report'}: {err['msg']}" for err in exc.errors()[:8]
        ]
    errors = []
    if report.agent != agent:
        errors.append(f"agent is {report.agent}, expected {agent}")
    for tool in report.tools_used:
        if not _tool_was_called(tool, called):
            errors.append(f"tools_used names {tool}, which was not called in this run")
    for number, finding in enumerate(report.findings):
        if not _tool_was_called(finding.evidence.tool, called):
            errors.append(f"findings.{number}.evidence.tool {finding.evidence.tool} was not called in this run")
    return (None, errors) if errors else (report, [])
