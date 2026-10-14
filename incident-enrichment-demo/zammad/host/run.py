#!/usr/bin/env python3
"""Start the official Zammad images without the Docker socket.

Docker is installed on this machine and 130G is free, but this agent
cannot open /var/run/docker.sock (the user is not in the docker group,
and sudo is not available). The images are the same ones Docker Compose
uses. bubblewrap runs them on the host network.

Postgres on this host already uses 5432 for another app, so Zammad's
database listens on 5433. Elasticsearch is left off; Zammad uses its
database search.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(os.environ.get("ZAMMAD_ROOT", "/home/cursor/var/zammad"))
UID = os.getuid()
GID = os.getgid()
PG_PORT = "5433"


def bwrap(
    name: str,
    rootfs: Path,
    binds: list[tuple[Path, str]],
    env: dict[str, str],
    argv: list[str],
    chdir: str = "",
) -> None:
    log = ROOT / "logs" / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "bwrap",
        "--unshare-user",
        "--uid",
        str(UID),
        "--gid",
        str(GID),
        "--unshare-pid",
        "--bind",
        str(rootfs),
        "/",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/run",
        "--tmpfs",
        "/dev/shm",
        "--ro-bind",
        "/etc/resolv.conf",
        "/etc/resolv.conf",
        "--ro-bind",
        "/etc/hosts",
        "/etc/hosts",
    ]
    for src, dest in binds:
        src.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--bind", str(src), dest])
    for key, value in env.items():
        cmd.extend(["--setenv", key, value])
    if chdir:
        cmd.extend(["--chdir", chdir])
    cmd.append("--")
    cmd.extend(argv)
    handle = log.open("ab")
    subprocess.Popen(cmd, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    print("started", name, flush=True)


def ensure_user(rootfs: Path) -> None:
    passwd = rootfs / "etc" / "passwd"
    group = rootfs / "etc" / "group"
    line = f"cursor:x:{UID}:{GID}:cursor:/tmp:/bin/sh\n"
    if passwd.is_file() and f":x:{UID}:" not in passwd.read_text(errors="replace"):
        with passwd.open("a") as handle:
            handle.write(line)
    if group.is_file() and f":x:{GID}:" not in group.read_text(errors="replace"):
        with group.open("a") as handle:
            handle.write(f"cursor:x:{GID}:\n")


def main() -> None:
    base = ROOT / "rootfs"
    data = ROOT / "data"
    pg = base / "postgres"
    redis = base / "redis"
    mem = base / "memcached"
    zammad = base / "zammad"
    for path in (pg, redis, mem, zammad):
        if not path.is_dir():
            raise SystemExit(f"missing rootfs {path}")
    for path in (pg, redis, mem, zammad):
        ensure_user(path)

    which = os.environ.get("ZAMMAD_PROC", "deps")
    init_dir = data / "pg-init"
    init_dir.mkdir(parents=True, exist_ok=True)
    script = init_dir / "10-create-zammad-role.sh"
    script.write_text(
        """#!/bin/bash
set -o errexit
psql --variable ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \\
  --variable role="$ZAMMAD_DB_USER" --variable pass="$ZAMMAD_DB_PASS" --variable db="$ZAMMAD_DB" <<'EOSQL'
CREATE ROLE :"role" LOGIN PASSWORD :'pass';
CREATE DATABASE :"db" OWNER :"role";
EOSQL
"""
    )
    script.chmod(0o755)

    if which == "deps":
        _start_deps(pg, redis, mem, data, init_dir)
        return

    _start_zammad(zammad, data, which)


def _start_deps(pg: Path, redis: Path, mem: Path, data: Path, init_dir: Path) -> None:
    bwrap(
        "postgres",
        pg,
        [(data / "pg", "/var/lib/postgresql/data"), (init_dir, "/docker-entrypoint-initdb.d")],
        {
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "zammad",
            "POSTGRES_DB": "postgres",
            "ZAMMAD_DB": "zammad_production",
            "ZAMMAD_DB_USER": "zammad",
            "ZAMMAD_DB_PASS": "zammad",
            "PGDATA": "/var/lib/postgresql/data",
            "PGPORT": PG_PORT,
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        },
        ["docker-entrypoint.sh", "postgres", "-p", PG_PORT],
    )
    bwrap(
        "redis",
        redis,
        [(data / "redis", "/data")],
        {},
        ["redis-server", "--bind", "127.0.0.1"],
    )
    bwrap(
        "memcached",
        mem,
        [],
        {},
        ["memcached", "-m", "256", "-l", "127.0.0.1"],
    )


def _start_zammad(zammad: Path, data: Path, which: str) -> None:
    zammad_env = {
        "POSTGRESQL_DB": "zammad_production",
        "POSTGRESQL_HOST": "127.0.0.1",
        "POSTGRESQL_USER": "zammad",
        "POSTGRESQL_PASS": "zammad",
        "POSTGRESQL_PORT": PG_PORT,
        "POSTGRESQL_DB_CREATE": "false",
        "REDIS_URL": "redis://127.0.0.1:6379",
        "MEMCACHE_SERVERS": "127.0.0.1:11211",
        "ELASTICSEARCH_ENABLED": "false",
        "NGINX_PORT": "8080",
        "ZAMMAD_RAILSSERVER_HOST": "127.0.0.1",
        "ZAMMAD_RAILSSERVER_PORT": "3010",
        "ZAMMAD_WEBSOCKET_HOST": "127.0.0.1",
        "ZAMMAD_WEBSOCKET_PORT": "6042",
        "ZAMMAD_FQDN": os.environ.get("ZAMMAD_FQDN", "${COMMAND_BOX_HOST}:8080"),
        "ZAMMAD_HTTP_TYPE": "http",
        "RAILS_ENV": "production",
        "RAILS_LOG_TO_STDOUT": "true",
        "RAILS_SERVE_STATIC_FILES": "true",
        "GEM_HOME": "/usr/local/bundle",
        "BUNDLE_PATH": "/usr/local/bundle",
        "BUNDLE_DEPLOYMENT": "1",
        "BUNDLE_WITHOUT": "test development",
        "ZAMMAD_DOCKER": "true",
        "HOME": "/tmp",
        "SSL_CERT_FILE": "/etc/ssl/certs/ca-certificates.crt",
        "REQUESTS_CA_BUNDLE": "/etc/ssl/certs/ca-certificates.crt",
        "LD_LIBRARY_PATH": "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu",
        "LANG": "C.UTF-8",
        "PATH": "/usr/local/bundle/ruby/current/bin:/usr/local/bundle/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "TZ": "UTC",
    }
    secret = Path.home() / "secrets" / "incident-enrichment.env"
    wizard = ""
    if secret.is_file():
        vals = {}
        for line in secret.read_text().splitlines():
            if line.startswith("ZAMMAD_") and "=" in line:
                key, value = line.split("=", 1)
                vals[key] = value.strip().strip("'").strip('"')
        user = vals.get("ZAMMAD_USER") or "oncall@metal-store.lab"
        password = vals.get("ZAMMAD_PASSWORD") or ""
        if password:
            import json

            import base64

            wizard = base64.b64encode(
                json.dumps(
                    {
                        "Users": [
                            {
                                "login": user,
                                "firstname": "On",
                                "lastname": "Call",
                                "email": user,
                                "password": password,
                                "roles": ["Admin", "Agent"],
                            }
                        ]
                    }
                ).encode()
            ).decode()
    # The wizard file is already on disk. Do not put the admin
    # password on the process command line.
    del wizard
    storage = data / "storage"
    backup = data / "backup"
    binds = [(storage, "/opt/zammad/storage"), (backup, "/var/tmp/zammad")]
    argv = {
        "init": ["zammad-init"],
        "railsserver": ["zammad-railsserver"],
        "nginx": ["zammad-nginx"],
        "websocket": ["zammad-websocket"],
        "scheduler": ["zammad-scheduler"],
    }[which]
    argv = ["/opt/zammad/bin/docker-entrypoint", *argv]
    bwrap(which, zammad, binds, zammad_env, argv, chdir="/opt/zammad")


if __name__ == "__main__":
    main()
