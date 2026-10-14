"""IDSP access tokens on an MCP resource server.

Lab MCP apps (vcf-mcp, tanzu-mcp) historically accepted only a static
capability token. Tanzu Agent Builder then used that token from CUPS and
skipped OAuth, so revoking the IDSP Grant did not deny on the wire.

This module is the product path for that door:

1. Serve RFC 9728 Protected Resource Metadata with no bearer (so the
   gateway and Agent Builder can discover IDSP).
2. On 401, advertise that metadata in WWW-Authenticate (RFC 9728 §5.1).
3. Accept an IDSP JWT whose ``aud`` includes this resource and whose
   ``scope`` shows AgentMinder granted this agent something here. Two
   shapes, both product: an **intent** scope
   (``urn:iam:agent:intent:<job>``, 2026-09-20) or a legacy tool-name
   scope (``vcf_call``, ``tools``). With an intent on the token the AI
   Gateway has already mapped tool -> job -> policy; this door does not
   redo that by tool name. That is how a third-party MCP behind the
   gateway behaves: verify the token, do not re-authorize per tool.
4. Keep the static lab token for ops (Number One recover), not for the
   talk agents once OAuth is discovered.

Copied onto the live CF apps at push time. Canonical copy is this file.
Never log bearer values.
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.request
from typing import Any, Iterable

# No trailing slash. Agent Builder RFC 8414 path-inserts this into
# /.well-known/oauth-authorization-server/<tenant>. A trailing slash
# makes IDSP treat the tenant as "default/" and return 400.
DEFAULT_ISSUER = "https://${AGENTMINDER_HOST}/default"
DEFAULT_JWKS = "https://${AGENTMINDER_HOST}/default/oauth2/v1/jwks"
OPR_PATHS = (
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
)

_jwks_lock = threading.Lock()
_jwks_cache: tuple[float, dict[str, Any]] | None = None
_JWKS_TTL = 300.0


def issuer() -> str:
    raw = (os.environ.get("IDSP_ISSUER") or DEFAULT_ISSUER).strip()
    return raw.rstrip("/")


def jwks_uri() -> str:
    return (os.environ.get("IDSP_JWKS_URI") or DEFAULT_JWKS).strip()


def resource_url(*, default: str) -> str:
    return (os.environ.get("MCP_RESOURCE_URL") or default).strip().rstrip("/")


def audiences(*, default_resource: str) -> list[str]:
    extra = (os.environ.get("IDSP_AUDIENCES") or "").strip()
    out = [resource_url(default=default_resource)]
    if extra:
        out.extend(p.strip() for p in extra.split(",") if p.strip())
    # Sidecar Mode: IDSP primaryAudience is the AI Gateway frontend URL
    # (docs: AI Resource Servers — Primary Audience = URL that consumes
    # the RS). Tokens minted with that resource fail if this env is still
    # the lab-mcp-gw back door.
    gw = (os.environ.get("IDSP_GATEWAY_RESOURCE") or "").strip()
    if gw:
        out.append(gw.rstrip("/"))
    # unique, stable order
    seen: set[str] = set()
    uniq: list[str] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


# Sidecar Mode / AI Gateway tokens carry Grant tool names, not a blanket
# ``tools`` scope. ``vcf-mcp-read`` privileges are these six read tools.
VCF_READ_SCOPES = (
    "vcf_targets",
    "vcf_search_api",
    "vcf_describe_api",
    "vcf_validate",
    "vcf_inventory",
    "vcf_audit",
    "vcf_list_vms",
    "vcf_get_vm",
    "vcf_vm_power_state",
    "vcf_list_networks",
    "vcf_list_segments",
    "vcf_list_gateways",
    "vcf_list_datastores",
    "vcf_get_datastore",
    "vcf_datastore_policy",
    "vcf_list_alerts",
    "vcf_ops_snapshot",
    "vcf_networks",
    "vcf_storage",
    "vcf_metrics",
)
VCF_WRITE_SCOPES = (
    "vcf_call",
    "vcf_task",
    "vcf_start_vm",
    "vcf_stop_vm",
    "vcf_reset_vm",
    "vcf_suspend_vm",
    "vcf_vms",
)
TANZU_LOOK_SCOPES = ("tp_targets", "tp_search_api", "tp_describe_api")
TANZU_RUN_SCOPES = ("tp_call", "tp_job")
# AgentMinder intent (job) scope. IDSP puts one on the token only when an
# authorization policy on THIS resource server grants that job to the
# agent, and only when the token was minted for this resource (aud).
INTENT_SCOPE_PREFIX = "urn:iam:agent:intent:"


def required_scopes() -> list[str]:
    raw = (os.environ.get("IDSP_REQUIRED_SCOPES") or "tools").strip()
    return [s for s in raw.split() if s]


def expand_read_scopes(needed: Iterable[str]) -> list[str]:
    """Honor named Grant scopes when the door still asks for blanket ``tools``.

    AgentMinder Sidecar Mode mints ``resource=`` the AI Gateway URL. That
    access token lists ``vcf_targets`` and friends, not ``tools``. A door
    that only intersects on ``tools`` 401s a valid Grant.
    """
    reads = [s for s in needed if s]
    if "tools" not in reads:
        return reads
    extra = list(VCF_READ_SCOPES) + list(TANZU_LOOK_SCOPES)
    return list(dict.fromkeys(reads + extra))


def protected_resource(*, default_resource: str, scopes: Iterable[str], name: str) -> dict[str, Any]:
    sc = list(scopes) if scopes else required_scopes()
    return {
        "resource": resource_url(default=default_resource),
        "authorization_servers": [issuer()],
        "bearer_methods_supported": ["header"],
        "scopes_supported": sc,
        "resource_name": name,
    }


def www_authenticate(*, metadata_url: str, resource: str) -> str:
    return (
        f'Bearer realm="mcp", resource_metadata="{metadata_url}", '
        f'resource="{resource}"'
    )


def is_opr_path(path: str) -> bool:
    p = (path or "").split("?", 1)[0]
    return p in OPR_PATHS


def looks_like_jwt(token: str) -> bool:
    if token.count(".") != 2:
        return False
    header, payload, sig = token.split(".")
    return bool(header and payload and sig)


def _scope_set(claim: Any) -> set[str]:
    if isinstance(claim, str):
        return {p for p in claim.split() if p}
    if isinstance(claim, (list, tuple)):
        return {str(p) for p in claim if p}
    return set()


def _aud_list(claim: Any) -> list[str]:
    if claim is None:
        return []
    if isinstance(claim, str):
        return [claim]
    if isinstance(claim, (list, tuple)):
        return [str(x) for x in claim if x]
    return []


def audience_ok(claims: dict[str, Any], allowed: Iterable[str]) -> bool:
    allowed_set = {a.rstrip("/") for a in allowed}
    for aud in _aud_list(claims.get("aud")):
        if aud.rstrip("/") in allowed_set:
            return True
    return False


def grant_ok(claims: dict[str, Any], needed: Iterable[str]) -> bool:
    have = _scope_set(claims.get("scope")) | _scope_set(claims.get("scp"))
    need = {s for s in needed if s}
    if not need:
        return False
    return bool(have & need)


def mutating_grant(claims: dict[str, Any], write_scopes: Iterable[str]) -> bool:
    have = _scope_set(claims.get("scope")) | _scope_set(claims.get("scp"))
    return bool(have & {s for s in write_scopes if s})


def intent_scopes(claims: dict[str, Any] | None) -> list[str]:
    """AgentMinder job names on the token (``urn:iam:agent:intent:*``)."""
    if not isinstance(claims, dict):
        return []
    have = _scope_set(claims.get("scope")) | _scope_set(claims.get("scp"))
    return sorted(s for s in have if s.startswith(INTENT_SCOPE_PREFIX))


def intent_grant(claims: dict[str, Any] | None) -> bool:
    """True when the AI Gateway path granted a job. Tool choice is the gateway's."""
    return bool(intent_scopes(claims))


def _ssl_ctx() -> ssl.SSLContext:
    if (os.environ.get("IDSP_TLS_VERIFY") or "").strip().lower() in ("0", "false", "no"):
        return ssl._create_unverified_context()
    # Lab AgentMinder often uses the lab CA; default to unverified unless asked.
    if (os.environ.get("IDSP_TLS_VERIFY") or "").strip().lower() in ("1", "true", "yes"):
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def _load_jwks() -> dict[str, Any]:
    global _jwks_cache
    now = time.time()
    with _jwks_lock:
        if _jwks_cache and _jwks_cache[0] > now:
            return _jwks_cache[1]
    req = urllib.request.Request(jwks_uri(), method="GET")
    with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=10) as resp:
        doc = json.loads(resp.read().decode())
    if not isinstance(doc, dict) or not isinstance(doc.get("keys"), list):
        raise ValueError("jwks document missing keys")
    with _jwks_lock:
        _jwks_cache = (now + _JWKS_TTL, doc)
    return doc


def verify_idsp_jwt(token: str) -> dict[str, Any] | None:
    """Return claims if this is a live IDSP access token, else None.

    Does not decide Grant; callers use grant_ok / audience_ok.
    """
    try:
        import jwt  # PyJWT — already on the vcf-mcp / tanzu-mcp droplets
        from jwt import PyJWK
    except ImportError:
        return None
    if not looks_like_jwt(token):
        return None
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None
    kid = header.get("kid")
    try:
        jwks = _load_jwks()
    except Exception:
        return None
    key = None
    for item in jwks.get("keys") or []:
        if not isinstance(item, dict):
            continue
        if kid and item.get("kid") != kid:
            continue
        try:
            key = PyJWK.from_dict(item).key
            break
        except Exception:
            continue
    if key is None:
        return None
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256", "ES256"],
            options={
                "verify_aud": False,  # we match aud ourselves (multi-value + gateway)
                "verify_iss": False,
                "require": ["exp", "iss"],
            },
        )
    except Exception:
        return None
    if not isinstance(claims, dict):
        return None
    got = str(claims.get("iss") or "").rstrip("/")
    want = issuer().rstrip("/")
    if got != want:
        return None
    return claims


def classify_idsp(
    presented: str | None,
    *,
    default_resource: str,
    read_scopes: Iterable[str],
    write_scopes: Iterable[str] = (),
) -> str | None:
    """Map an IDSP JWT to 'admin' | 'read' | None.

    A token that carries an AgentMinder intent for this resource is
    'admin' here: the gateway in front already decided which tools that
    job allows and strips the rest. Re-checking tool names would refuse
    every intent-only grant (the 2026-09-20 "Backend unavailable" 2002
    was this door's 401). Legacy tool-name scopes still work unchanged.
    """
    if not presented or not looks_like_jwt(presented):
        return None
    claims = verify_idsp_jwt(presented)
    if not claims:
        return None
    if not audience_ok(claims, audiences(default_resource=default_resource)):
        return None
    writes = list(write_scopes)
    reads = expand_read_scopes(read_scopes)
    if writes and mutating_grant(claims, writes):
        return "admin"
    if grant_ok(claims, reads or writes):
        return "read"
    if intent_grant(claims):
        return "admin"
    return None
