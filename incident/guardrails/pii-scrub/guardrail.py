"""Deterministic on-stage reply for a contact-details message.

The model was answering that beat with a refusal and a prompt to say
"pick up the latest incident ticket". The chat shows this text instead.
The prompt is already masked before this runs. Do not log the text.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

_KINDS = (
    ("name", "[NAME]"),
    ("email", "[EMAIL]"),
    ("phone", "[PHONE]"),
    ("card", "[CARD]"),
    ("SSN", "[SSN]"),
)
_NAG = re.compile(
    r"[^.!?\n]*(?:pick up the latest incident ticket|trigger phrase|placeholder text)[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)
_LOCK = threading.Lock()
_STATE = {"until": 0.0, "line": None, "sent": False, "strip": False}


def status() -> str:
    with _LOCK:
        if time.monotonic() > _STATE["until"]:
            return "off"
        if _STATE["line"]:
            return "line"
        if _STATE["strip"]:
            return "strip"
        return "off"


def reset() -> None:
    with _LOCK:
        _STATE.update(until=0.0, line=None, sent=False, strip=False)


def is_enrichment(text: str) -> bool:
    low = text.lower()
    return ("pick up" in low and "ticket" in low) or (
        "enrich" in low and ("ticket" in low or "incident" in low)
    )


def last_user_text(body: dict[str, Any]) -> str:
    found = ""
    for message in body.get("messages") or []:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        found = _flatten(message.get("content"))
    return found


def _flatten(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(_flatten(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in parts if part)
    return ""


def compose(masked: str) -> str | None:
    """The line the chat must show, plus the masked complaint. None if no PII."""
    shown = [f"{label} {token}" for label, token in _KINDS if token in masked]
    if not shown:
        return None
    summary = strip_nag(" ".join(masked.split()))
    if not any(token in summary for _, token in _KINDS):
        summary = " ".join(masked.split())
    if len(summary) > 400:
        summary = summary[:400].rstrip() + "…"
    return (
        "PII guardrail: masked before the model saw it — "
        + ", ".join(shown)
        + "\n"
        + summary
    )


def strip_nag(text: str) -> str:
    kept = _NAG.sub("", text)
    kept = re.sub(r"\n{3,}", "\n\n", kept).strip()
    if kept:
        return kept
    return "Tell me what you want checked. I will not start an incident unless you ask."


def _texts(body: Any) -> list[str]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("content", "text") and isinstance(value, str) and value.strip():
                    found.append(value)
                elif isinstance(value, (dict, list)):
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(body)
    return found


def _focus(text: str) -> str:
    """The contact lines, when they were pasted into a long playbook prompt."""
    positions = [text.find(token) for _, token in _KINDS if token in text]
    if not positions:
        return text
    start = min(positions)
    previous = text.rfind("\n", 0, start)
    start = 0 if previous < 0 else previous + 1
    return text[start:start + 500]


def _arm(line: str | None, strip: bool) -> None:
    with _LOCK:
        pending = (
            _STATE["line"] is not None
            and not _STATE["sent"]
            and time.monotonic() < _STATE["until"]
        )
        if line is None and pending:
            return
        _STATE["until"] = time.monotonic() + 90
        _STATE["line"] = line
        _STATE["sent"] = False
        _STATE["strip"] = strip


def observe_prompt(body: dict[str, Any]) -> None:
    """Remember a masked contact message so the next reply is the guardrail line.

    The agent often pastes the playbook and the user text into one system
    string. That playbook contains the ticket phrase, so a user-role check
    misses the contact details and would skip the guardrail.
    """
    blobs = [text for text in _texts(body) if any(token in text for _, token in _KINDS)]
    if blobs:
        chosen = min(blobs, key=len)
        line = compose(_focus(chosen))
        if line:
            # A contact message is not an incident. Hide tools so the
            # model cannot open or enrich a ticket on this turn.
            body.pop("tools", None)
            body.pop("tool_choice", None)
            _arm(line, False)
            return
    user = last_user_text(body)
    if not user or is_enrichment(user):
        return
    _arm(None, True)


def apply_response(body: Any) -> Any:
    """Replace the model reply for a contact message, or cut the ticket nag."""
    with _LOCK:
        if time.monotonic() > _STATE["until"]:
            return body
        line = _STATE["line"]
        sent = bool(_STATE["sent"])
        strip = bool(_STATE["strip"])
    if line:
        wrote = _fill_content(body, "" if sent else line)
        if wrote and not sent:
            with _LOCK:
                _STATE["sent"] = True
        return body
    if strip:
        _map_content(body, strip_nag)
    return body


# Stream chunks put the words under content, text, or reasoning_content.
# Skip ids and role names. Any other sentence is the reply the chat shows.
_SKIP_REPLY_KEYS = frozenset(
    {"id", "model", "object", "system_fingerprint", "role", "finish_reason", "index", "created"}
)
_SKIP_REPLY_VALUES = frozenset({"assistant", "user", "system", "stop", "length", "tool_calls"})


def _reply_text(key: str, value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and key not in _SKIP_REPLY_KEYS
        and value.strip() not in _SKIP_REPLY_VALUES
    )


def _fill_content(body: Any, text: str) -> bool:
    wrote = False

    def visit(node: Any) -> None:
        nonlocal wrote
        if isinstance(node, dict):
            for key, value in node.items():
                if _reply_text(key, value):
                    node[key] = text if not wrote else ""
                    wrote = True
                elif isinstance(value, (dict, list)):
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, str) and item.strip() and item.strip() not in _SKIP_REPLY_VALUES:
                    # Lists have no key. Replace the sentence in place.
                    pass
                visit(item) if not isinstance(item, str) else None
            for index, item in enumerate(node):
                if isinstance(item, str) and item.strip() and item.strip() not in _SKIP_REPLY_VALUES:
                    node[index] = text if not wrote else ""
                    wrote = True

    visit(body)
    return wrote


def _map_content(body: Any, fn) -> None:
    if isinstance(body, dict):
        for key, value in list(body.items()):
            if _reply_text(key, value):
                body[key] = fn(value)
            elif isinstance(value, (dict, list)):
                _map_content(value, fn)
    elif isinstance(body, list):
        for index, item in enumerate(body):
            if isinstance(item, str) and item.strip() and item.strip() not in _SKIP_REPLY_VALUES:
                body[index] = fn(item)
            else:
                _map_content(item, fn)
