#!/usr/bin/env python3
"""Inject or restore latency on the store's database path.

Inject does not scale Postgres. It uses the approved fault account to
run the storage-load pod, which adds a 10 second sleep to catalog
queries. The store stays up and answers HTTP 200 slowly.

Restore removes that sleep. If Postgres was scaled to 0, restore scales
it back to 1 and waits until the store answers HTTP 200. It does not
create a database pod.

Kubernetes calls go through the Tanzu Kubernetes door, not kubectl.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import storage_load  # noqa: E402
from orchestrator.k8s import call as k8s_call  # noqa: E402
from orchestrator.orchestrator import store_status  # noqa: E402

NS = "metal-music-store"
DEPLOY = "postgres"


def scale(replicas: int) -> str:
    """The door's service account may not hold deployments/scale. A refusal
    is reported, and the pod step still runs."""
    try:
        out = k8s_call(
            "k8s_scale_deployment",
            {"name": DEPLOY, "namespace": NS, "replicas": replicas},
            write=True,
            timeout=70,
        )
    except RuntimeError as exc:
        return f"scale deploy/{DEPLOY} {replicas} refused: {str(exc)[:160]}"
    shown = out.get("replicas")
    return f"scale deploy/{DEPLOY} {replicas}: {shown if shown is not None else replicas}"


def delete_postgres_pods() -> list[str]:
    """Remove every live Postgres pod. The service selects all of them."""
    notes: list[str] = []
    listed = k8s_call("k8s_list_pods", {"namespace": NS}, timeout=40)
    for row in listed.get("pods") or []:
        name = str(row.get("name") or "")
        phase = str(row.get("phase") or "")
        if not name.startswith("postgres"):
            continue
        if phase in ("Succeeded", "Failed"):
            notes.append(f"left {name} {phase}")
            continue
        try:
            deleted = k8s_call(
                "k8s_delete_pod", {"name": name, "namespace": NS}, write=True, timeout=70
            )
            notes.append(f"deleted {deleted.get('name') or name}")
        except RuntimeError as exc:
            text = str(exc)
            if "404" in text or "not found" in text.lower():
                notes.append(f"{name} already absent")
            else:
                notes.append(f"{name}: {text}")
    return notes


def inject() -> int:
    """Slow the database path. Leave Postgres running."""
    running = _running_postgres()
    if not running:
        print("Postgres is not running, so database latency was not applied.")
        return 1
    print("running " + ", ".join(running))
    return storage_load.apply_delay()


def _running_postgres() -> list[str]:
    listed = k8s_call("k8s_list_pods", {"namespace": NS}, timeout=40)
    return [
        str(row.get("name") or "")
        for row in (listed.get("pods") or [])
        if str(row.get("name") or "").startswith("postgres") and str(row.get("phase") or "") == "Running"
    ]


def restore() -> int:
    """Remove the query delay and wait until the store is fast and HTTP 200."""
    notes: list[str] = []
    if not _running_postgres():
        notes.append(scale(1))
        deadline = time.time() + 180
        while time.time() < deadline and not _running_postgres():
            time.sleep(5)
    if not _running_postgres():
        notes.append("Postgres is not running, so the store cannot be restored.")
        print("\n".join(notes))
        return 1
    removed = storage_load.remove_delay()
    if removed != 0:
        notes.append("latency remove failed")
    deadline = time.time() + 180
    store: dict = {}
    running: list[str] = []
    problem = ""
    while time.time() < deadline:
        try:
            running = _running_postgres()
        except RuntimeError as exc:
            problem = str(exc)[:160]
            time.sleep(5)
            continue
        if not running:
            time.sleep(5)
            continue
        store = store_status()
        fast = isinstance(store.get("ms"), int) and store["ms"] < 5000
        if store.get("status") == 200 and fast:
            notes.append("running " + ", ".join(running))
            notes.append(f"store HTTP 200 in {store['ms']} ms")
            notes.append("store restored: HTTP 200")
            print("\n".join(notes))
            return 0
        time.sleep(5)
    if running:
        notes.append("running " + ", ".join(running))
    if problem:
        notes.append(problem)
    notes.append(f"store not restored: HTTP {store.get('status')} in {store.get('ms')} ms")
    print("\n".join(notes))
    return 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inject or restore database-path latency")
    parser.add_argument("--restore", action="store_true", help="Bring the database back")
    args = parser.parse_args()
    return restore() if args.restore else inject()


if __name__ == "__main__":
    sys.exit(main())
