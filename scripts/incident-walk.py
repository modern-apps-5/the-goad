#!/usr/bin/env python3
"""Slow catalog queries and open one Zammad ticket.

Does not call the agents and does not start a disk-write loop.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request

TITLE = "Metal Music Store slow: checkout and catalog pages taking 10+ seconds"
# Shop namespace Argo runs from gitops/music-store-apps.
NS = "music-store"

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


def kubectl(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["kubectl", *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def apply_delay() -> None:
    sql = APPLY_SQL.replace("\n", " ")
    job = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: catalog-delay
  namespace: {NS}
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: psql
          image: postgres:16-alpine
          env:
            - name: PGHOST
              value: postgres-service
            - name: PGUSER
              value: music_user
            - name: PGDATABASE
              value: music_store
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: store-db
                  key: password
            - name: DELAY_SQL
              value: {json.dumps(sql)}
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
            runAsNonRoot: true
            runAsUser: 999
          command: ["sh", "-c", "psql -v ON_ERROR_STOP=1 -c \\"$DELAY_SQL\\" && echo DELAY_APPLIED"]
"""
    kubectl("delete", "job", "catalog-delay", "-n", NS, "--ignore-not-found=true")
    applied = kubectl("apply", "-f", "-", input_text=job)
    if applied.returncode != 0:
        raise SystemExit(applied.stderr.strip() or "could not apply the delay job")
    deadline = time.time() + 180
    while time.time() < deadline:
        logs = kubectl("logs", "job/catalog-delay", "-n", NS)
        if "DELAY_APPLIED" in (logs.stdout or ""):
            print("Database latency applied: catalog queries sleep 10 seconds.")
            return
        time.sleep(3)
    raise SystemExit("The latency command did not apply.")


def store_slow() -> None:
    url = os.environ.get("STORE_URL", "").strip()
    if not url:
        raise SystemExit("STORE_URL is unset")
    req = urllib.request.Request(url)
    started = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        status = resp.status
        resp.read()
    elapsed_ms = int((time.time() - started) * 1000)
    print(f"store HTTP {status} in {elapsed_ms} ms")
    if status != 200 or elapsed_ms < 8000:
        raise SystemExit("The pages are not slow yet, so no incident ticket was opened.")


def open_ticket() -> None:
    base = os.environ.get("ZAMMAD_URL", "").strip().rstrip("/")
    token = os.environ.get("ZAMMAD_TOKEN", "").strip()
    if not base or not token:
        raise SystemExit("ZAMMAD_URL or ZAMMAD_TOKEN is unset")
    payload = {
        "title": TITLE,
        "group": "Users",
        # The Zammad admin, which the autowizard creates (gitops/platform-tools-apps).
        "customer": "admin@goad.gpu.set.lab",
        "article": {"subject": TITLE, "body": "Catalog pages are taking 10+ seconds.", "type": "note", "internal": False},
    }
    req = urllib.request.Request(
        base + "/api/v1/tickets",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Authorization": f"Token token={token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        doc = json.loads(resp.read().decode())
    print(f"opened ticket {doc.get('number') or doc.get('id')}: {TITLE}")
    print("The incident response agent can pick this ticket up in chat.")
    print("Enrichment was not started.")


def main() -> None:
    apply_delay()
    store_slow()
    open_ticket()


if __name__ == "__main__":
    main()
