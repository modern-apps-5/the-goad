"""The Metal Music Store topology, read from the static map file.

The order is fixed: store, then pods, then VMs, then datastore. The
incident response agent loads this file before it asks Jev anything.
"""

from __future__ import annotations

import json
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parents[1] / "topology" / "metal-music.json"
ORDER = ("store", "pods", "vms", "datastore")


def load(path: Path = MAP_PATH) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if tuple(doc.get("order") or ()) != ORDER:
        raise ValueError(f"{path.name}: order must be {', '.join(ORDER)}")
    vm_names = {vm["name"] for vm in doc["vms"]}
    for pod in doc["pods"]:
        if pod["vm"] not in vm_names:
            raise ValueError(f"{path.name}: pod {pod['name']} names VM {pod['vm']}, which is not in vms")
    for vm in doc["vms"]:
        if vm["datastore"] != doc["datastore"]["name"]:
            raise ValueError(f"{path.name}: VM {vm['name']} names datastore {vm['datastore']}, which is not the datastore")
    return doc


def _suffix(item: dict) -> str:
    """Platform and workload kind, when the map carries them."""
    extra = []
    if item.get("platform"):
        extra.append(f"platform {item['platform']}")
    if item.get("kind"):
        extra.append(f"kind {item['kind']}")
    if not extra:
        return ""
    return ", " + ", ".join(extra)


def rows(doc: dict) -> list[dict]:
    """One row per item, in map order, for the reasoning panel."""
    store = doc["store"]
    out = [{"order": 1, "layer": "store", "name": store["name"], "detail": f"{store['url']} in namespace {store['namespace']}{_suffix(store)}"}]
    out += [
        {"order": 2, "layer": "pod", "name": pod["name"], "detail": f"{pod['role']}, on {pod['vm']}{_suffix(pod)}"}
        for pod in doc["pods"]
    ]
    out += [
        {"order": 3, "layer": "VM", "name": vm["name"], "detail": f"{vm['vcenter_id']}, {vm['role']}, on {vm['datastore']}{_suffix(vm)}"}
        for vm in doc["vms"]
    ]
    ds = doc["datastore"]
    out.append({"order": 4, "layer": "datastore", "name": ds["name"], "detail": f"{ds['vcenter_id']}, {ds['type']}. {ds['shared_with']}{_suffix(ds)}"})
    return out


def text(doc: dict) -> str:
    """Short plain text for a prompt or a Jev state."""
    by_vm: dict[str, list[str]] = {}
    for pod in doc["pods"]:
        by_vm.setdefault(pod["vm"], []).append(pod["name"])
    store_bits = _suffix(doc["store"]).lstrip(", ")
    store_tail = f", {store_bits}." if store_bits else "."
    lines = [
        f"Store {doc['store']['name']} ({doc['store']['url']}), namespace {doc['store']['namespace']}{store_tail}",
        "Shoppers reach it through the Avi load balancer, which records response time. "
        "Slow pages show there as high response time.",
    ]
    for vm in doc["vms"]:
        pods = ", ".join(by_vm.get(vm["name"], [])) or "no store pods"
        lines.append(f"VM {vm['name']} ({vm['vcenter_id']}, {vm['role']}) runs {pods}.")
    ds = doc["datastore"]
    lines.append(
        f"Every VM is on datastore {ds['name']} ({ds['type']}), shared with the whole nest. "
        "Normal disk read latency on that datastore is about 5 to 11 ms. "
        "Write latency of hundreds of milliseconds is storage latency, and it makes the store's database queries slow."
    )
    return " ".join(lines)


def store_vms(doc: dict) -> list[str]:
    """Names of the VMs that run store pods, in map order."""
    used = {pod["vm"] for pod in doc["pods"]}
    return [vm["name"] for vm in doc["vms"] if vm["name"] in used]
