"""Presidio scrubber for AI Services tile webhook bodies.

The tile POSTs OpenAI chat JSON. We rewrite string fields the model
would see or echo. Do not log those strings — they are the PII.

Tokens are [EMAIL], [PHONE], [CARD], [SSN], and [NAME]. A name is
masked only in a string that already holds one of the other four.
Stock Presidio misses a 7-digit phone and some spaced card numbers,
so those shapes are Presidio pattern checks plus a Luhn test.
Driver-license and IP recognizers stay off: they rewrote tool ids.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

DEFAULT_ENTITIES = (
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
)

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_PHONE10 = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
)
_PHONE7 = re.compile(r"(?<!\d)\d{3}-\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_NAME_IS = re.compile(
    r"\b((?:[Mm]y name is|[Nn]ame is) )([A-Z][a-z]+(?: [A-Z][a-z]+)+)"
)

# OpenAI fields that hold natural language. Leave ids, roles, model names.
_SCRUB_KEYS = frozenset({"content", "text", "arguments", "refusal"})


def entities_from_env() -> tuple[str, ...]:
    raw = os.environ.get("PRESIDIO_ENTITIES", "").strip()
    if not raw:
        return DEFAULT_ENTITIES
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def language_from_env() -> str:
    return os.environ.get("PRESIDIO_LANGUAGE", "en").strip() or "en"


def luhn_ok(digits: str) -> bool:
    """True when `digits` is 13 to 19 digits and passes the Luhn check."""
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = ord(ch) - 48
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _sub(text: str, pattern: re.Pattern[str], token: str, ok: Callable[[str], bool] | None = None) -> tuple[str, bool]:
    changed = False

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        raw = match.group(0)
        if ok is not None and not ok(raw):
            return raw
        changed = True
        return token

    return pattern.sub(repl, text), changed


def _mask_cards(text: str) -> tuple[str, bool]:
    """Replace each Luhn span. A failed greedy span must not swallow the next one."""
    changed = False
    out: list[str] = []
    i = 0
    while i < len(text):
        match = _CARD.search(text, i)
        if match is None:
            out.append(text[i:])
            break
        raw = match.group(0)
        if luhn_ok(re.sub(r"\D", "", raw)):
            out.append(text[i:match.start()])
            out.append("[CARD]")
            changed = True
            i = match.end()
            continue
        out.append(text[i:match.start() + 1])
        i = match.start() + 1
    return "".join(out), changed


def mask_structured(text: str, entities: set[str] | None = None) -> tuple[str, bool]:
    """Replace email, SSN, phone, then Luhn card. Leave every other word."""
    wanted = entities if entities is not None else set(entities_from_env())
    hit = False
    if "EMAIL_ADDRESS" in wanted:
        text, changed = _sub(text, _EMAIL, "[EMAIL]")
        hit = hit or changed
    if "US_SSN" in wanted:
        text, changed = _sub(text, _SSN, "[SSN]")
        hit = hit or changed
    if "PHONE_NUMBER" in wanted:
        text, changed = _sub(text, _PHONE10, "[PHONE]")
        hit = hit or changed
        text, changed = _sub(text, _PHONE7, "[PHONE]")
        hit = hit or changed
    if "CREDIT_CARD" in wanted:
        text, changed = _mask_cards(text)
        hit = hit or changed
    return text, hit


def mask_names_fallback(text: str) -> str:
    """Mask a 'name is First Last' only. Used when the string already has other PII."""
    return _NAME_IS.sub(lambda match: match.group(1) + "[NAME]", text)


def apply_mask(
    text: str,
    person_fn: Callable[[str], str] | None = None,
    entities: set[str] | None = None,
) -> str:
    """Mask structured PII, then names in that same string."""
    if not text:
        return text
    wanted = entities if entities is not None else set(entities_from_env())
    masked, hit = mask_structured(text, wanted)
    if not hit or "PERSON" not in wanted:
        return masked
    if person_fn is not None:
        masked = person_fn(masked)
    return mask_names_fallback(masked)


def presidio_fn(
    entities: tuple[str, ...] | None = None,
    language: str | None = None,
) -> Callable[[str], str]:
    """Official Microsoft Presidio analyzer + anonymizer.

    Pin spaCy `en_core_web_sm`. AnalyzerEngine() with no config
    downloads `en_core_web_lg` (~400MB) at boot and OOMs a 512M
    Diego cell. The small model is the documented NlpEngineProvider
    path, not a homemade filter.
    """
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    from presidio_anonymizer.entities import OperatorConfig

    model = os.environ.get("PRESIDIO_SPACY_MODEL", "en_core_web_sm").strip()
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        }
    )
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
    anonymizer = AnonymizerEngine()
    lang = language or language_from_env()
    wanted = set(entities or entities_from_env())
    name_ops = {"PERSON": OperatorConfig("replace", {"new_value": "[NAME]"})}

    def person_fn(text: str) -> str:
        hits = analyzer.analyze(text=text, language=lang, entities=["PERSON"])
        if not hits:
            return text
        return anonymizer.anonymize(text=text, analyzer_results=hits, operators=name_ops).text

    def run(text: str) -> str:
        return apply_mask(text, person_fn, wanted)

    return run


class Scrubber:
    def __init__(self, rewrite: Callable[[str], str] | None = None) -> None:
        self._rewrite = rewrite if rewrite is not None else presidio_fn()

    def text(self, value: str) -> str:
        if not value:
            return value
        return self._rewrite(value)

    def obj(self, payload: Any) -> Any:
        return walk_openai(payload, self.text)


def walk_openai(payload: Any, rewrite: Callable[[str], str]) -> Any:
    """Copy JSON, rewriting OpenAI natural-language strings."""
    if isinstance(payload, list):
        return [walk_openai(item, rewrite) for item in payload]
    if not isinstance(payload, dict):
        return payload
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SCRUB_KEYS and isinstance(value, str):
            out[key] = rewrite(value)
        elif isinstance(value, (dict, list)):
            out[key] = walk_openai(value, rewrite)
        else:
            out[key] = value
    return out
