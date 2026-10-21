"""The incident response agent's reasoning, written as it happens.

Every call rewrites orchestrator/last-reasoning.json in one atomic move,
so the Grafana panel can read a whole record at any moment of a run.
No token, key, or password goes into this file.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

PATH = Path(os.environ.get("REASONING_PATH") or Path(__file__).resolve().parent / "last-reasoning.json")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# One row on the live board, in the order the audience reads them.
COMPONENTS = (
    "Incident response agent",
    "Jev",
    "K8s agent",
    "VCF agent",
    "LB agent",
    "Zammad",
    "AgentMinder",
)


class Reasoning:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        self.doc: dict = {
            "run_id": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            "started_at": _now(),
            "updated_at": _now(),
            "state": "running",
            "ticket": None,
            "saw": [],
            "topology": [],
            "agents": [],
            "jev": [],
            "steps": [],
            "timeline": [],
            "components": [{"component": name, "did": "Waiting.", "time": ""} for name in COMPONENTS],
            "pending_zammad": None,
            "audience": {
                "state": "running",
                "ticket_number": "",
                "title": "",
                "assessment": "",
                "jev_agents": None,
                "agents_called": [],
                "jev_route": None,
                "enrichment": "",
                "error": None,
            },
        }
        self._write()

    def _write(self) -> None:
        self.doc["updated_at"] = _now()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.doc, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def step(self, text: str) -> None:
        self.doc["steps"].append({"time": _now(), "step": text})
        self._write()

    def ticket(self, ticket: dict) -> None:
        self.doc["ticket"] = {"id": ticket.get("id"), "number": ticket.get("number"), "title": ticket.get("title")}
        self._write()

    def saw(self, source: str, what: str) -> None:
        self.doc["saw"].append({"time": _now(), "source": source, "what": what[:300]})
        self._write()

    def topology(self, rows: list[dict]) -> None:
        self.doc["topology"] = rows
        self._write()

    def jev(self, decision: str, choice: str | None, used: str | None, probabilities: dict, error: str | None,
            confidence: float | None = None) -> None:
        """One row per option, so the panel shows every probability, not only the winner.

        Jev's confidence in its pick is a separate number from the pick's probability; the 0.70 gate uses it.
        """
        pick = "Jev's pick" if confidence is None else f"Jev's pick, confidence {round(float(confidence), 2)}"
        if not probabilities:
            self.doc["jev"].append({"decision": decision, "option": choice or "none", "probability": None,
                                    "chosen": "no answer" if error else pick, "used": used, "error": error})
        for option, probability in sorted(probabilities.items(), key=lambda kv: -kv[1]):
            self.doc["jev"].append({
                "decision": decision,
                "option": option,
                "probability": round(float(probability), 3),
                "chosen": pick if option == choice else "",
                "used": "used" if option == used else "",
                "error": error,
            })
        self._write()

    def agent(self, agent: str, why: str) -> None:
        self.doc["agents"].append({"agent": agent, "why": why, "status": "calling", "tool_calls": None, "result": ""})
        self._write()

    def agent_done(self, agent: str, status: str, tool_calls: int, result: str) -> None:
        for row in self.doc["agents"]:
            if row["agent"] == agent and row["status"] == "calling":
                row.update({"status": status, "tool_calls": tool_calls, "result": result[:300]})
        self._write()

    def finish(self, state: str, summary: str = "") -> None:
        self.doc["state"] = state
        self.doc["summary"] = summary[:500]
        self.doc["audience"]["state"] = state
        if summary and not self.doc["audience"].get("assessment"):
            self.doc["audience"]["assessment"] = summary[:500]
        self._write()

    def event(self, text: str) -> None:
        """One line on the audience timeline."""
        self.doc["timeline"].append({"time": _now(), "event": text[:300]})
        self._write()

    def component(self, name: str, did: str) -> None:
        """Plain-English row for one part of the system."""
        stamp = _now()
        text = did[:500]
        for row in self.doc["components"]:
            if row["component"] == name:
                row["did"] = text
                row["time"] = stamp
                self._write()
                return
        self.doc["components"].append({"component": name, "did": text, "time": stamp})
        self._write()

    def audience(self, **fields: object) -> None:
        """What the incident response agent's chat should be able to say."""
        for key, value in fields.items():
            if key in self.doc["audience"]:
                self.doc["audience"][key] = value
        self._write()

    def pending_zammad(self, ticket_id: int, note: str, priority: str, group: str, tags: list[str]) -> None:
        """The helpdesk write happens on agents-machine, which can reach Zammad."""
        self.doc["pending_zammad"] = {
            "ticket_id": ticket_id,
            "note": note,
            "priority": priority,
            "group": group,
            "tags": tags,
        }
        self._write()
