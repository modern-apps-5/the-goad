"""VCF diagnostic tools. Each one calls vcf-mcp on 127.0.0.1:8092.

Numbers below are copied from that door. This module does not invent a
capacity, a percent, or an alarm.
"""

from __future__ import annotations

import os

from diagnostics.doors import load_local, streamable

NS = "metal-music-store"


def _call(tool: str, args: dict | None = None) -> dict:
    load_local()
    url = os.environ.get("VCF_MCP_URL") or "http://127.0.0.1:8092/mcp"
    token = os.environ.get("VCF_READ_TOKEN") or ""
    if not token:
        raise RuntimeError("VCF_READ_TOKEN is unset")
    return streamable(url, token, tool, args or {})


def _items(doc: dict) -> list:
    if isinstance(doc.get("items"), list):
        return doc["items"]
    body = doc.get("body")
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("value", "items", "results"):
            if isinstance(body.get(key), list):
                return body[key]
    return []


def vcf_vm_health(_args: dict) -> dict:
    doc = _call("vcf_list_vms")
    rows = []
    for item in _items(doc)[:30]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("name"),
                "power_state": item.get("power_state") or item.get("powerState"),
                "cpu_count": item.get("cpu_count") or item.get("cpuCount"),
                "memory_mib": item.get("memory_size_MiB") or item.get("memorySizeMiB"),
            }
        )
    return {"count": doc.get("count"), "shown": len(rows), "vms": rows, "source": "vcf-mcp vcf_list_vms"}


def vcf_host_health(_args: dict) -> dict:
    doc = _call("vcf_call", {"target": "vcenter", "method": "GET", "path": "/api/vcenter/host"})
    rows = []
    for item in _items(doc)[:20]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("name"),
                "host": item.get("host"),
                "connection_state": item.get("connection_state") or item.get("connectionState"),
                "power_state": item.get("power_state") or item.get("powerState"),
            }
        )
    return {"count": doc.get("count") or len(rows), "hosts": rows, "source": "vcf-mcp vcf_call /api/vcenter/host"}


def vcf_host_resources(_args: dict) -> dict:
    """CPU and memory from vCenter host records when the API returns them.

    Utilization percents are included only when the payload has them.
    """
    doc = _call("vcf_call", {"target": "vcenter", "method": "GET", "path": "/api/vcenter/host"})
    rows = []
    missing = []
    for item in _items(doc)[:12]:
        if not isinstance(item, dict):
            continue
        cpu = item.get("cpu") if isinstance(item.get("cpu"), dict) else {}
        memory = item.get("memory") if isinstance(item.get("memory"), dict) else {}
        row = {
            "name": item.get("name"),
            "connection_state": item.get("connection_state") or item.get("connectionState"),
            "cpu_mhz": cpu.get("mhz") or item.get("cpu_mhz"),
            "memory_mib": memory.get("size_MiB") or item.get("memory_size_MiB"),
        }
        if not row["cpu_mhz"] and not row["memory_mib"]:
            missing.append(item.get("name"))
        rows.append(row)
    note = None
    if missing:
        note = (
            "The host list did not include CPU or memory figures for "
            f"{len(missing)} hosts. No utilization percent was invented."
        )
    return {"hosts": rows, "note": note, "source": "vcf-mcp vcf_call /api/vcenter/host"}


def _datastore_rows(type_name: str | None) -> dict:
    listing = _call("vcf_list_datastores")
    rows = []
    for item in _items(listing):
        if not isinstance(item, dict):
            continue
        ident = item.get("datastore") or item.get("id")
        kind = item.get("type")
        if type_name and str(kind).upper() != type_name:
            continue
        detail = item
        if ident and ("free_space" not in item and "capacity" not in item):
            detail = _call("vcf_get_datastore", {"datastore": ident})
            body = detail.get("body") if isinstance(detail.get("body"), dict) else detail
            if isinstance(body, dict):
                detail = {**item, **body}
        capacity = detail.get("capacity")
        free = detail.get("free_space") or detail.get("freeSpace")
        used_pct = None
        if isinstance(capacity, (int, float)) and isinstance(free, (int, float)) and capacity:
            used_pct = round(100.0 * (capacity - free) / capacity, 1)
        rows.append(
            {
                "name": detail.get("name") or item.get("name"),
                "type": kind,
                "capacity_bytes": capacity,
                "free_bytes": free,
                "used_percent": used_pct,
            }
        )
        if len(rows) >= 8:
            break
    return {"count": len(rows), "datastores": rows}


def vcf_datastore_capacity(_args: dict) -> dict:
    out = _datastore_rows(None)
    out["source"] = "vcf-mcp vcf_list_datastores"
    return out


def vcf_vsan_capacity(_args: dict) -> dict:
    out = _datastore_rows("VSAN")
    out["source"] = "vcf-mcp datastores of type VSAN"
    if not out["datastores"]:
        out["note"] = "No VSAN datastore was in the vCenter list returned by vcf-mcp."
    return out


def vcf_alarms(_args: dict) -> dict:
    doc = _call("vcf_list_alerts")
    rows = []
    for item in _items(doc)[:15]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "name": item.get("alertName") or item.get("name") or item.get("alertDefinitionName"),
                "status": item.get("status") or item.get("alertStatus"),
                "criticality": item.get("alertLevel") or item.get("criticality") or item.get("severity"),
                "resource": item.get("resourceName") or item.get("resourceId") or item.get("objectName"),
                "start": item.get("startTimeUTC") or item.get("startTime"),
            }
        )
    return {
        "count": doc.get("count"),
        "shown": len(rows),
        "alarms": rows,
        "error": doc.get("error"),
        "source": "vcf-mcp vcf_list_alerts",
    }


def vcf_disk_latency(args: dict) -> dict:
    """Disk latency of the store's VMs from VCF Operations, through vcf-mcp."""
    from orchestrator import topology

    vms = args.get("vms") or topology.store_vms(topology.load())
    doc = _call("vcf_vm_disk_latency", {"vms": list(vms)})
    doc["source"] = "vcf-mcp vcf_vm_disk_latency"
    return doc


TOOLS = {
    "vcf_vm_health": vcf_vm_health,
    "vcf_host_health": vcf_host_health,
    "vcf_host_resources": vcf_host_resources,
    "vcf_datastore_capacity": vcf_datastore_capacity,
    "vcf_vsan_capacity": vcf_vsan_capacity,
    "vcf_alarms": vcf_alarms,
    "vcf_disk_latency": vcf_disk_latency,
}
