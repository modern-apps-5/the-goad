#!/usr/bin/env python3
"""Storage latency fault: a disk-heavy pod on a VM that shares the store's datastore.

Every VM in the nest, the store's three worker nodes included, sits on the
one vSAN datastore ${VSAN_DATASTORE}. This pod runs on worker VM
${K8S_NODE_B} and writes 1 GiB at a time
with direct I/O, over and over, so the writes reach vSAN instead of the
page cache. If the image's dd has no direct I/O, each pass is synced to
disk instead. It stops itself after 15 minutes even if nobody runs stop.

    python3 fault-injection/storage_load.py start
    python3 fault-injection/storage_load.py stop
    python3 fault-injection/storage_load.py status

Kubernetes calls go through the Kubernetes MCP door, not kubectl. The
image is the store's own Postgres image, already on the node, so nothing
is pulled. VCF Operations collects every five minutes, so the latency
reaches vcf_vm_disk_latency about one collection after start.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.k8s import call as k8s_call  # noqa: E402

NS = "metal-music-store"
POD = "storage-load"
NODE = "${K8S_NODE_B}"
IMAGE_FROM = "postgres"
DEADLINE_SECONDS = 900
LOOP = (
    "i=0; while true; do i=$((i+1)); "
    "dd if=/dev/zero of=/scratch/load bs=1M count=1024 oflag=direct conv=fsync 2>/dev/null "
    "|| dd if=/dev/zero of=/scratch/load bs=1M count=1024 conv=fsync 2>/dev/null || sleep 1; "
    "rm -f /scratch/load; echo pass $i; done"
)


def image() -> str:
    deploy = k8s_call("k8s_get", {"kind": "deployment", "name": IMAGE_FROM, "namespace": NS}, timeout=40)
    containers = deploy["object"]["spec"]["template"]["spec"]["containers"]
    return containers[0]["image"]


def pod_spec(node: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": POD, "namespace": NS, "labels": {"app": POD, "demo": "storage-latency"}},
        "spec": {
            "nodeName": node,
            "restartPolicy": "Never",
            "activeDeadlineSeconds": DEADLINE_SECONDS,
            "terminationGracePeriodSeconds": 2,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 999,
                "runAsGroup": 999,
                "fsGroup": 999,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "load",
                    "image": image(),
                    "command": ["sh", "-c", LOOP],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                        "runAsNonRoot": True,
                        "runAsUser": 999,
                        "runAsGroup": 999,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "resources": {"requests": {"cpu": "100m", "memory": "64Mi"},
                                  "limits": {"cpu": "500m", "memory": "128Mi"}},
                    "volumeMounts": [{"name": "scratch", "mountPath": "/scratch"}],
                }
            ],
            "volumes": [{"name": "scratch", "emptyDir": {"sizeLimit": "2Gi"}}],
        },
    }


def status() -> dict | None:
    try:
        doc = k8s_call("k8s_get", {"kind": "pod", "name": POD, "namespace": NS}, timeout=40)
    except RuntimeError as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            return None
        raise
    obj = doc.get("object") or {}
    return {"phase": (obj.get("status") or {}).get("phase"), "node": (obj.get("spec") or {}).get("nodeName"),
            "started": (obj.get("status") or {}).get("startTime")}


# Catalog reads sleep 10 seconds. The view keeps the album columns, so the
# store still answers HTTP 200. Restore drops the view and renames the table back.
APPLY_SQL = """
DO $body$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'albums' AND c.relkind = 'r'
  ) THEN
    ALTER TABLE albums RENAME TO albums_data;
    EXECUTE 'CREATE VIEW albums AS SELECT a.* FROM albums_data a CROSS JOIN (SELECT pg_sleep(10) AS nap) n';
  END IF;
END
$body$;
"""

UNDO_SQL = """
DROP VIEW IF EXISTS albums;
DO $body$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'albums_data' AND c.relkind = 'r'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = 'albums' AND c.relkind = 'r'
  ) THEN
    ALTER TABLE albums_data RENAME TO albums;
  END IF;
END
$body$;
ALTER SYSTEM RESET log_min_duration_statement;
SELECT pg_reload_conf();
"""

LOG_SQL = """
ALTER SYSTEM SET log_min_duration_statement = '1000';
SELECT pg_reload_conf();
"""


def _db_password() -> str:
    deploy = k8s_call("k8s_get", {"kind": "deployment", "name": IMAGE_FROM, "namespace": NS}, timeout=40)
    containers = deploy["object"]["spec"]["template"]["spec"]["containers"]
    for item in containers[0].get("env") or []:
        if item.get("name") == "POSTGRES_PASSWORD" and item.get("value"):
            return str(item["value"])
    raise RuntimeError("postgres password is not on the deployment")


def command_pod(shell: str) -> dict:
    """The approved storage-load shape, with this shell as its command."""
    spec = pod_spec(NODE)
    container = spec["spec"]["containers"][0]
    container["command"] = ["sh", "-c", shell]
    container["env"] = [
        {"name": "PGHOST", "value": "postgres-service"},
        {"name": "PGUSER", "value": "music_user"},
        {"name": "PGDATABASE", "value": "music_store"},
        {"name": "PGPASSWORD", "value": _db_password()},
    ]
    return spec


def _wait_absent(seconds: int = 60) -> bool:
    import time
    deadline = time.time() + seconds
    while time.time() < deadline:
        if status() is None:
            return True
        time.sleep(2)
    return status() is None


def _create(shell: str) -> int:
    current = status()
    if current is not None:
        try:
            k8s_call("k8s_delete_pod", {"name": POD, "namespace": NS}, write=True, timeout=40)
        except RuntimeError as exc:
            if "404" not in str(exc) and "not found" not in str(exc).lower():
                print(f"Not started. The Kubernetes door refused: {str(exc)[:240]}")
                return 1
        if not _wait_absent():
            print(f"{POD} is still present, so the latency command was not started.")
            return 1
    try:
        created = k8s_call("k8s_create_pod", {"pod": command_pod(shell)}, write=True, timeout=40)
    except RuntimeError as exc:
        print(f"Not started. The Kubernetes door refused: {str(exc)[:240]}")
        return 1
    print(f"Started {created.get('name') or POD}.")
    return 0


def _wait_marker(marker: str, seconds: int = 90) -> bool:
    import time
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            doc = k8s_call("k8s_pod_logs", {"name": POD, "namespace": NS, "tail": 40}, timeout=40)
        except RuntimeError:
            time.sleep(3)
            continue
        if marker in str(doc.get("log") or ""):
            return True
        time.sleep(3)
    return False


def apply_delay() -> int:
    """Slow catalog queries by 10 seconds. The store stays up."""
    current = status()
    if current and current.get("phase") == "Running" and _wait_marker("DELAY_APPLIED", seconds=20):
        print("Database latency applied: catalog queries sleep 10 seconds.")
        return 0
    shell = (
        "psql -v ON_ERROR_STOP=1 <<'SQL'\n" + APPLY_SQL + "SQL\n"
        "psql <<'SQL'\n" + LOG_SQL + "SQL\n"
        "echo DELAY_APPLIED\n"
        "while true; do sleep 30; done\n"
    )
    if _create(shell) != 0:
        return 1
    if not _wait_marker("DELAY_APPLIED"):
        print("The latency command did not apply.")
        return 1
    print("Database latency applied: catalog queries sleep 10 seconds.")
    return 0


def remove_delay() -> int:
    """Drop the slow view and restore the albums table."""
    shell = "psql -v ON_ERROR_STOP=1 <<'SQL'\n" + UNDO_SQL + "SQL\necho DELAY_REMOVED\n"
    if _create(shell) != 0:
        return 1
    if not _wait_marker("DELAY_REMOVED", seconds=90):
        print("The latency command did not remove.")
        return 1
    try:
        k8s_call("k8s_delete_pod", {"name": POD, "namespace": NS}, write=True, timeout=40)
    except RuntimeError as exc:
        if "404" not in str(exc) and "not found" not in str(exc).lower():
            print(f"Latency removed. The pod delete was refused: {str(exc)[:160]}")
            return 1
    print("Database latency removed.")
    return 0


def start(node: str) -> int:
    current = status()
    if current and current["phase"] in ("Pending", "Running"):
        print(f"{POD} is already {current['phase']} on {current['node']} since {current['started']}.")
        return 0
    if current:
        k8s_call("k8s_delete_pod", {"name": POD, "namespace": NS}, write=True, timeout=40)
    try:
        created = k8s_call("k8s_create_pod", {"pod": pod_spec(node)}, write=True, timeout=40)
    except RuntimeError as exc:
        print(f"Not started. The Kubernetes door refused: {str(exc)[:240]}")
        return 1
    print(f"Started {created.get('name')} on {node}. It writes 1 GiB with direct I/O in a loop and stops "
          f"itself after {DEADLINE_SECONDS // 60} minutes. Stop it sooner with: "
          "python3 fault-injection/storage_load.py stop")
    return 0


def stop() -> int:
    try:
        k8s_call("k8s_delete_pod", {"name": POD, "namespace": NS}, write=True, timeout=40)
    except RuntimeError as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            print(f"{POD} is not running.")
            return 0
        print(f"Not stopped. The Kubernetes door refused: {str(exc)[:240]}")
        return 1
    print(f"Stopped {POD}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start or stop the storage latency load")
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--node", default=NODE, help="Worker VM to run on")
    args = parser.parse_args()
    if args.action == "start":
        return start(args.node)
    if args.action == "stop":
        return stop()
    current = status()
    print(f"{POD}: {current['phase']} on {current['node']} since {current['started']}" if current
          else f"{POD} is not running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
