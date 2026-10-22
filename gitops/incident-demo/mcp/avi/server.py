#!/usr/bin/env python3
"""Standalone Avi MCP for the incident demo.

This process is not vcf-mcp. It talks to the Avi controller only.
Diagnostic tools are read-only.
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import last_metric, oper_state, reason_text, results, session, vip_of
from mcp_http import McpServer, Tool, serve

HERE = Path(__file__).resolve().parent
METRICS_LATENCY = "l7_client.avg_client_txn_latency,l4_client.avg_total_rtt"
METRICS_ERRORS = (
    "l7_client.avg_resp_4xx,l7_client.avg_resp_5xx,"
    "l7_client.avg_complete_responses,l7_client.avg_error_responses"
)


def _load_env_file() -> None:
    path = Path(os.environ.get("AVI_MCP_ENV") or (Path.home() / "secrets" / "avi-mcp.env"))
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


PLACEHOLDER = re.compile(r"<[A-Z_]+>")


def _match(item: dict, name: str) -> bool:
    """Substring match. The model path's PII filter rewrites parts of some
    names to placeholders such as <US_DRIVER_LICENSE>, so a placeholder
    matches any text and the visible parts must appear in order."""
    if not name:
        return True
    have = str(item.get("name") or "").lower()
    if not PLACEHOLDER.search(name):
        return name.lower() in have
    pattern = ".+?".join(re.escape(part.lower()) for part in PLACEHOLDER.split(name))
    return re.search(pattern, have) is not None


def _limit(args: dict, default: int = 8) -> int:
    try:
        value = int(args.get("limit") if args.get("limit") is not None else default)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, 20))


def avi_vs_health(args: dict) -> dict:
    avi = session()
    name = str(args.get("name") or "").strip()
    doc = avi.get("/api/virtualservice?page_size=50")
    rows = []
    for item in results(doc):
        if not _match(item, name):
            continue
        uuid = item.get("uuid")
        runtime = avi.get(f"/api/virtualservice/{uuid}/runtime") if uuid else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        rows.append(
            {
                "name": item.get("name"),
                "uuid": uuid,
                "enabled": item.get("enabled"),
                "oper_state": oper_state(runtime),
                "reason": reason_text(runtime),
                "vip": vip_of(item, avi),
            }
        )
        if len(rows) >= _limit(args):
            break
    return {
        "controller": avi.controller,
        "version": avi.version,
        "count": doc.get("count") if isinstance(doc, dict) else len(rows),
        "shown": len(rows),
        "virtual_services": rows,
    }


def avi_pool_member_health(args: dict) -> dict:
    avi = session()
    name = str(args.get("name") or "").strip()
    doc = avi.get("/api/pool?page_size=50")
    rows = []
    for item in results(doc):
        if not _match(item, name):
            continue
        uuid = item.get("uuid")
        runtime = avi.get(f"/api/pool/{uuid}/runtime") if uuid else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        members = []
        servers = runtime.get("servers") or runtime.get("server_detail") or []
        if not servers and uuid:
            try:
                extra = avi.get(f"/api/pool/{uuid}/runtime/server")
            except RuntimeError:
                extra = {}
            if isinstance(extra, dict):
                servers = extra.get("results") or extra.get("servers") or []
            elif isinstance(extra, list):
                servers = extra
        for server in servers if isinstance(servers, list) else []:
            if not isinstance(server, dict):
                continue
            ip = server.get("ip") or {}
            addr = ip.get("addr") if isinstance(ip, dict) else server.get("ip_addr") or server.get("hostname")
            members.append(
                {
                    "addr": addr,
                    "port": server.get("port"),
                    "oper_state": oper_state(server),
                    "enabled": server.get("enabled"),
                }
            )
        rows.append(
            {
                "name": item.get("name"),
                "oper_state": oper_state(runtime),
                "servers_up": runtime.get("num_servers_up"),
                "servers": runtime.get("num_servers"),
                "members": members[:20],
            }
        )
        if len(rows) >= _limit(args):
            break
    return {"controller": avi.controller, "shown": len(rows), "pools": rows}


# Analytics on the nested controller often never answers. The AI Gateway
# drops the backend call at 30 seconds and the agent sidecar then waits
# out its own long timeout. A metrics read must finish well inside that.
METRIC_TIMEOUT = int(os.environ.get("AVI_METRIC_TIMEOUT") or 5)


def _metrics(uuid: str, metric_id: str, timeout: int = METRIC_TIMEOUT) -> dict:
    avi = session()
    path = (
        f"/api/analytics/metrics/virtualservice/{uuid}"
        f"?metric_id={metric_id}&limit=3&step=30&pad_missing_data=false"
    )
    doc = avi.get(path, timeout=timeout)
    series = doc.get("series") if isinstance(doc, dict) else []
    return {
        "metrics": [last_metric(item) for item in series or [] if isinstance(item, dict)],
    }


def _empty_metrics(metrics: list) -> bool:
    if not metrics:
        return True
    return all(item.get("value") is None for item in metrics)


def health_finding(vs: dict | None, pool: dict | None) -> str:
    """One sentence from real VIP and pool health. Empty when health was not read.

    The healthy sentence is only for an up VIP and an up pool with every
    member up. A missing pool is not treated as healthy.
    """
    if not isinstance(vs, dict) or not vs.get("oper_state"):
        return ""
    state = str(vs.get("oper_state"))
    enabled = vs.get("enabled")
    vip = vs.get("vip") or "the VIP"
    if isinstance(vip, list):
        vip = ", ".join(str(item) for item in vip) or "the VIP"
    if state != "OPER_UP" or enabled is False:
        return f"VIP {vip} is {state}."
    if not isinstance(pool, dict) or not pool.get("oper_state"):
        return ""
    oper = str(pool.get("oper_state"))
    up = pool.get("servers_up")
    total = pool.get("servers")
    if oper != "OPER_UP" or up == 0:
        return f"VIP is OPER_UP but pool {pool.get('name') or ''} is {oper}.".strip()
    if up is not None and total is not None and up < total:
        return f"VIP is OPER_UP but {up} of {total} pool members are up."
    return "LB healthy, no latency anomaly at the VIP"


def _pool_ref(item: dict) -> str:
    ref = item.get("pool_ref") or ""
    if isinstance(ref, str) and "/api/pool/" in ref:
        return ref.rstrip("/").rsplit("/", 1)[-1]
    return ""


def _runtime_row(path: str, name: str, timeout: int) -> dict:
    avi = session()
    try:
        runtime = avi.get(path, timeout=timeout)
    except (TimeoutError, OSError, RuntimeError):
        return {}
    if not isinstance(runtime, dict):
        return {}
    return {"name": name, "oper_state": oper_state(runtime), "enabled": runtime.get("enabled"),
            "servers_up": runtime.get("num_servers_up"), "servers": runtime.get("num_servers")}


def _health_pair(item: dict, timeout: int) -> tuple[dict, dict | None]:
    """VIP and pool health for one virtual service. Snapshot first, then one runtime each."""
    name = str(item.get("name") or "")
    vs = _snapshot_match("avi_vs_health", "virtual_services", name) or {}
    pool = _snapshot_match("avi_pool_member_health", "pools", name)
    if vs.get("oper_state") and pool and pool.get("oper_state"):
        return vs, pool
    if not vs.get("oper_state") and item.get("uuid") and timeout > 0:
        live = _runtime_row(f"/api/virtualservice/{item['uuid']}/runtime", name, timeout)
        if live.get("oper_state"):
            vs = {**live, "vip": vs.get("vip") or [], "enabled": item.get("enabled", live.get("enabled"))}
    if (not pool or not pool.get("oper_state")) and timeout > 0:
        pool_id = _pool_ref(item)
        if pool_id:
            live_pool = _runtime_row(f"/api/pool/{pool_id}/runtime", name, timeout)
            if live_pool.get("oper_state"):
                pool = live_pool
    return vs, pool


def _snapshot_match(view: str, key: str, name: str) -> dict | None:
    with _snapshot_lock:
        hit = _snapshots.get(view)
    if not hit or not name:
        return None
    rows = hit[1].get(key) or []
    if not isinstance(rows, list):
        return None
    low = name.lower()
    for row in rows:
        if isinstance(row, dict) and str(row.get("name") or "").lower() == low:
            return row
    for row in rows:
        if not isinstance(row, dict):
            continue
        have = str(row.get("name") or "").lower()
        if low in have or have in low:
            return row
    return None


def _one_vs(args: dict) -> tuple[object, dict | None, list[str]]:
    """The virtual service named in args: exact name, then uuid, then substring.

    No name means the first one. A miss returns None and the valid names,
    so the agent can retry with one of them instead of failing its run.
    """
    avi = session()
    name = str(args.get("name") or "").strip()
    rows = results(avi.get("/api/virtualservice?page_size=50", timeout=METRIC_TIMEOUT))
    names = [str(item.get("name") or "") for item in rows]
    if not name:
        return avi, (rows[0] if rows else None), names
    for test in (
        lambda item: str(item.get("name") or "") == name,
        lambda item: str(item.get("uuid") or "") == name,
        lambda item: _match(item, name),
    ):
        for item in rows:
            if test(item):
                return avi, item, names
    return avi, None, names


def _no_match(avi, args: dict, names: list[str]) -> dict:
    return {
        "controller": avi.controller,
        "matched": False,
        "asked": str(args.get("name") or ""),
        "note": "No virtual service matched. Call again with one of these names.",
        "names": names[:50],
    }


def _estate_health() -> dict:
    """VIP and pool health from the snapshot. No analytics call, so it cannot sit for minutes.

    The store has no Avi virtual service of its own (its ingress is nginx). The
    honest read is every virtual service and pool already in the snapshot.
    """
    with _snapshot_lock:
        vs_hit = _snapshots.get("avi_vs_health")
        pool_hit = _snapshots.get("avi_pool_member_health")
    vs_rows = (vs_hit[1].get("virtual_services") if vs_hit else None) or []
    pool_rows = (pool_hit[1].get("pools") if pool_hit else None) or []
    if not isinstance(vs_rows, list):
        vs_rows = []
    if not isinstance(pool_rows, list):
        pool_rows = []
    vs_up = sum(1 for row in vs_rows if isinstance(row, dict) and row.get("oper_state") == "OPER_UP" and row.get("enabled") is not False)
    pools_up = sum(1 for row in pool_rows if isinstance(row, dict) and row.get("oper_state") == "OPER_UP")
    short = [
        row for row in pool_rows
        if isinstance(row, dict) and row.get("servers") is not None and row.get("servers_up") is not None
        and row["servers_up"] < row["servers"]
    ]
    body = {
        "metrics": [],
        "virtual_services": len(vs_rows),
        "virtual_services_up": vs_up,
        "pools": len(pool_rows),
        "pools_up": pools_up,
        "members_short": len(short),
        "note": "Latency series was empty. VIP and pool health are the Avi snapshot.",
    }
    if vs_hit:
        body["as_of"] = _stamp(vs_hit[0])
    if vs_rows and pool_rows and vs_up == len(vs_rows) and pools_up == len(pool_rows) and not short:
        body["oper_state"] = "OPER_UP"
        body["finding"] = "LB healthy, no latency anomaly at the VIP"
    elif vs_rows or pool_rows:
        body["finding"] = (
            f"{vs_up} of {len(vs_rows)} virtual services are OPER_UP. "
            f"{pools_up} of {len(pool_rows)} pools are OPER_UP."
        )
    else:
        body["note"] = "Avi health snapshot is not ready. Latency was not read."
    return body


def _latency_body(args: dict, metric_id: str, *, with_finding: bool) -> dict:
    """Metrics, or VIP and pool health when the series is empty or too slow."""
    try:
        avi, item, names = _one_vs(args)
    except (TimeoutError, OSError):
        return {"timed_out": True, "matched": False, "note": "Avi did not answer in time.", "metrics": []}
    if item is None:
        if with_finding:
            # A miss must not hand back a name list. That made the agent call again.
            return {"controller": avi.controller, **_estate_health()}
        return _no_match(avi, args, names)
    uuid = str(item.get("uuid") or "")
    timed_out = False
    try:
        metrics = _metrics(uuid, metric_id) if uuid else {"metrics": []}
    except (TimeoutError, OSError):
        metrics = {"metrics": []}
        timed_out = True
    except RuntimeError as exc:
        metrics = {"metrics": []}
        note = str(exc)[:180]
    else:
        note = ""
    body = {
        "controller": avi.controller,
        "name": item.get("name"),
        "vip": [],
        **metrics,
    }
    series = metrics.get("metrics") or []
    if not with_finding or not (timed_out or _empty_metrics(series)):
        if not timed_out:
            body["vip"] = vip_of(item, avi)
            return body
    vs, pool = _health_pair(item, METRIC_TIMEOUT)
    if vs.get("vip"):
        body["vip"] = vs.get("vip")
    elif not body["vip"]:
        body["vip"] = vip_of(item, avi)
    body["oper_state"] = vs.get("oper_state") or ""
    body["enabled"] = vs.get("enabled", item.get("enabled"))
    if pool:
        body["pool"] = {
            "name": pool.get("name"),
            "oper_state": pool.get("oper_state"),
            "servers_up": pool.get("servers_up"),
            "servers": pool.get("servers"),
        }
    sentence = health_finding(vs if vs.get("oper_state") else None, pool)
    if sentence:
        body["finding"] = sentence
    if timed_out:
        body["timed_out"] = True
        body["note"] = "Latency metrics did not answer in time. VIP and pool health are from Avi."
    elif _empty_metrics(series):
        body["note"] = note or "Latency series was empty. VIP and pool health are from Avi."
    return body


def avi_latency(args: dict) -> dict:
    return _latency_body(args, METRICS_LATENCY, with_finding=True)


def avi_error_rates(args: dict) -> dict:
    return _latency_body(args, METRICS_ERRORS, with_finding=False)


def avi_se_state(args: dict) -> dict:
    avi = session()
    name = str(args.get("name") or "").strip()
    doc = avi.get("/api/serviceengine?page_size=25")
    rows = []
    for item in results(doc):
        if not _match(item, name):
            continue
        uuid = item.get("uuid")
        runtime = avi.get(f"/api/serviceengine/{uuid}/runtime") if uuid else {}
        runtime = runtime if isinstance(runtime, dict) else {}
        rows.append(
            {
                "name": item.get("name"),
                "oper_state": oper_state(runtime),
                "reason": reason_text(runtime),
                "connected": runtime.get("se_connected"),
                "powered": runtime.get("power_state") or runtime.get("powerstate"),
            }
        )
        if len(rows) >= _limit(args, 6):
            break
    return {
        "controller": avi.controller,
        "version": avi.version,
        "count": doc.get("count") if isinstance(doc, dict) else len(rows),
        "service_engines": rows,
    }


# The nested controller answers one runtime call per object, and a full
# health view took 29 to 51 seconds. The AI Gateway drops a backend call
# after 30 seconds and the caller then waits out its own timeout. So the
# two whole-estate views come from a snapshot refreshed in the background,
# stamped with as_of. A call that names one object stays live.
SNAPSHOT_SECONDS = int(os.environ.get("AVI_SNAPSHOT_SECONDS") or 60)
SNAPSHOT_VIEWS = {
    "avi_vs_health": lambda: avi_vs_health({"limit": 20}),
    "avi_pool_member_health": lambda: avi_pool_member_health({"limit": 20}),
}
_snapshots: dict[str, tuple[float, dict]] = {}
_snapshot_lock = threading.Lock()


def _stamp(when: float) -> str:
    return datetime.fromtimestamp(when, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _refresh(view: str) -> dict:
    value = SNAPSHOT_VIEWS[view]()
    with _snapshot_lock:
        _snapshots[view] = (time.time(), value)
    return value


def _refresh_forever() -> None:
    while True:
        for view in SNAPSHOT_VIEWS:
            try:
                _refresh(view)
            except Exception:
                pass
        time.sleep(SNAPSHOT_SECONDS)


def _from_snapshot(view: str, live: Callable[[dict], dict]) -> Callable[[dict], dict]:
    def handler(args: dict) -> dict:
        if str(args.get("name") or "").strip():
            return {**live(args), "as_of": _stamp(time.time())}
        with _snapshot_lock:
            hit = _snapshots.get(view)
        if hit and time.time() - hit[0] < SNAPSHOT_SECONDS * 3:
            return {**hit[1], "as_of": _stamp(hit[0])}
        return {**_refresh(view), "as_of": _stamp(time.time())}

    return handler


def build() -> McpServer:
    read = os.environ.get("MCP_READ_TOKEN") or ""
    write = os.environ.get("MCP_WRITE_TOKEN") or ""
    server = McpServer("avi-mcp", "1.0.0", read, write)
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Optional name substring"},
            "limit": {"type": "integer"},
        },
    }
    server.add(
        Tool(
            "avi_vs_health",
            "Virtual service oper state and VIP. Without a name, every virtual service as of the last snapshot (as_of).",
            schema,
            _from_snapshot("avi_vs_health", avi_vs_health),
            read_only=True,
        )
    )
    server.add(
        Tool(
            "avi_pool_member_health",
            "Pool member health. Without a name, every pool as of the last snapshot (as_of).",
            schema,
            _from_snapshot("avi_pool_member_health", avi_pool_member_health),
            read_only=True,
        )
    )
    server.add(Tool(
        "avi_latency",
        "Recent virtual service latency. If the series is empty or slow, returns VIP and pool health and a finding.",
        schema,
        avi_latency,
        read_only=True,
    ))
    server.add(Tool("avi_error_rates", "Recent 4xx, 5xx, and error responses.", schema, avi_error_rates, read_only=True))
    server.add(Tool("avi_se_state", "Service engine oper state.", schema, avi_se_state, read_only=True))
    try:
        avi = session()
        server.health_extra = {
            "controller": avi.controller,
            "version": avi.version,
            "connected": True,
        }
    except Exception as exc:
        server.health_extra = {"connected": False, "error": str(exc)[:180]}
    # The refresh also keeps the controller session from going idle, so a
    # call does not pay for a fresh sign-in.
    threading.Thread(target=_refresh_forever, name="avi-snapshot", daemon=True).start()
    return server


def main() -> None:
    _load_env_file()
    # Cloud Foundry sets PORT and the process must take every interface.
    # A desktop run keeps the host from MCP_HOST.
    if os.environ.get("PORT"):
        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ["PORT"])
    else:
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("MCP_PORT", "8093"))
    serve(build(), host, port)


if __name__ == "__main__":
    main()
