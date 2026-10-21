"""Load one agent skill into the Qwen system prompt."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROLE_SKILL = {
    "orchestrator": "incident_response_agent",
    "incident_response_agent": "incident_response_agent",
    "logs-specialist": "k8s_diagnostic_agent",
    "platform-specialist": "k8s_diagnostic_agent",
    "k8s_diagnostic_agent": "k8s_diagnostic_agent",
    "lb_diagnostic_agent": "lb_diagnostic_agent",
    "vcf_diagnostic_agent": "vcf_diagnostic_agent",
    "writer": "writer",
}


def load_skill(role: str) -> tuple[str, str, str]:
    """Return folder, version, and the skill text.

    Version comes from the frontmatter line `version:`. Missing file
    returns an empty text and version `missing`.
    """
    folder = ROLE_SKILL.get(role, role)
    path = ROOT / "skills" / folder / "SKILL.md"
    if not path.is_file():
        print(f"skill {folder} version missing")
        return folder, "missing", ""
    text = path.read_text(encoding="utf-8")
    version = "unversioned"
    for line in text.splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break
    print(f"skill {folder} version {version} loaded")
    return folder, version, text
