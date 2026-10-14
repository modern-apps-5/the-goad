"""OpenAI-compatible client for Qwen on the DGX.

Reads DGX_BASE_URL, DGX_MODEL, and DGX_API_KEY from the environment.
Does not print the key or the URL.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from orchestrator.envfile import load_env


def config() -> tuple[str, str, str]:
    load_env()
    base = os.environ.get("DGX_BASE_URL", "").rstrip("/")
    model = os.environ.get("DGX_MODEL", "qwen3.5:122b-a10b")
    key = os.environ.get("DGX_API_KEY", "")
    if not base:
        raise RuntimeError("DGX_BASE_URL is unset. Copy .env.example to .env.")
    return base, model, key


def _request(
    url: str,
    key: str,
    payload: dict | None = None,
    timeout: int = 20,
    extra_headers: dict | None = None,
) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Accept": "application/json", "User-Agent": "incident-enrichment-demo"}
    if extra_headers:
        headers.update(extra_headers)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        if key:
            body = body.replace(key, "[redacted]")
        raise RuntimeError(f"HTTP {exc.code} dgx-api {body}") from exc
    except OSError as exc:
        raise RuntimeError(f"unreachable dgx-api: {type(exc).__name__}") from exc


def complete(
    messages: list[dict],
    *,
    max_tokens: int = 800,
    timeout: int = 180,
    temperature: float = 0.2,
    model: str | None = None,
    traffic_class: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[str, int | None, int | None, str]:
    """Chat completion. Returns text, prompt tokens, completion tokens, model id.

    traffic_class "demo" is the live-demo door on the gate. Bulk callers
    stay on the default and can be refused while a demo lock is on.
    reasoning_effort "none" turns Qwen thinking off; enable_thinking and
    think are ignored by this endpoint.
    """
    base, default_model, key = config()
    use = model or default_model
    extra = {"X-Llamagate-Class": traffic_class} if traffic_class else None
    payload = {
        "model": use,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    body = _request(
        f"{base}/chat/completions",
        key,
        payload,
        timeout=timeout,
        extra_headers=extra,
    )
    usage = body.get("usage") or {}
    choice = (body.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    if not str(text).strip():
        text = msg.get("reasoning") or msg.get("reasoning_content") or ""
    return str(text), usage.get("prompt_tokens"), usage.get("completion_tokens"), body.get("model") or use
