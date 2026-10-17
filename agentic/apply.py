#!/usr/bin/env python3
"""Apply the agentic demo onto the music-store guest cluster.

Reads blanks from the environment. Does not print tokens or passwords.
Skips CLM when CLM_IMAGE is empty. Does not start demo.sh.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = ("STORE_HOST", "ZAMMAD_HOST", "GRAFANA_HOST", "POSTGRES_HOST", "USERS_HOST", "ZAMMAD_DB_PASSWORD", "GRAFANA_ADMIN_PASSWORD", "QWEN_BASE_URL", "QWEN_API_KEY")


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is unset")
    return value


def run(args: list[str], *, input_text: str | None = None) -> None:
    proc = subprocess.run(args, input=input_text, text=True, capture_output=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(detail or f"command failed: {args[0]}")
    if proc.stdout.strip():
        print(proc.stdout.strip())


def fill(text: str) -> str:
    for name in (
        "STORE_HOST",
        "ZAMMAD_HOST",
        "GRAFANA_HOST",
        "POSTGRES_HOST",
        "USERS_HOST",
        "ZAMMAD_DB_PASSWORD",
        "PROMETHEUS_URL",
    ):
        text = text.replace("${" + name + "}", os.environ.get(name, "http://prometheus.example.invalid" if name == "PROMETHEUS_URL" else ""))
    return text


def wizard_b64() -> str:
    """Same autowizard shape as the host copy. Password stays in the env."""
    password = need("ZAMMAD_ADMIN_PASSWORD")
    user = os.environ.get("ZAMMAD_ADMIN_USER", "agent@example.lab").strip()
    payload = {
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
    return base64.b64encode(json.dumps(payload).encode()).decode()


def store_password() -> str:
    text = (ROOT.parent / "app" / "music-store" / "k8s-deployment.yaml").read_text()
    for line in text.splitlines():
        if "music_password" in line and "DB_PASSWORD" not in line:
            # the value line is the next assignment; handled below
            pass
    # The published manifest sets DB_PASSWORD to this literal.
    marker = 'value: "music_password"'
    if marker not in text:
        raise SystemExit("shop database password is not in the published store manifest")
    return "music_password"


def ensure_admin_password() -> None:
    if os.environ.get("ZAMMAD_ADMIN_PASSWORD", "").strip():
        return
    os.environ["ZAMMAD_ADMIN_PASSWORD"] = secrets.token_urlsafe(18)
    os.environ.setdefault("ZAMMAD_ADMIN_USER", "agent@example.lab")
    path = Path("/tmp/goad-demo.env")
    if path.is_file():
        with path.open("a") as handle:
            handle.write(f"ZAMMAD_ADMIN_USER={os.environ['ZAMMAD_ADMIN_USER']}\n")
            handle.write(f"ZAMMAD_ADMIN_PASSWORD={os.environ['ZAMMAD_ADMIN_PASSWORD']}\n")


def _apply_secret(k: list[str], args: list[str]) -> None:
    built = subprocess.run(k + args, capture_output=True, text=True, check=True)
    run(k + ["apply", "-f", "-"], input_text=built.stdout)


def ensure_mcp_secrets(k: list[str]) -> None:
    ns = "metal-music-app-agentic-system"
    run(k + ["apply", "-f", str(ROOT / "mcp" / "rbac.yaml")])
    token = subprocess.run(
        k + ["create", "token", "goad-k8s-mcp", "-n", ns, "--duration=24h"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    kube_path = Path(tempfile.mkdtemp()) / "config"
    kube_path.write_text(
        "apiVersion: v1\nkind: Config\n"
        "clusters:\n- name: music-store\n  cluster:\n"
        "    server: https://kubernetes.default.svc\n"
        "    insecure-skip-tls-verify: true\n"
        "contexts:\n- name: music-store\n  context:\n"
        "    cluster: music-store\n    user: mcp\n"
        "    namespace: metal-music-store\n"
        "current-context: music-store\n"
        "users:\n- name: mcp\n  user:\n"
        f"    token: {token}\n"
    )
    kube_path.chmod(0o600)
    _apply_secret(k, [
        "create", "secret", "generic", "guest-kubeconfig", "-n", ns,
        f"--from-file=config={kube_path}", "--dry-run=client", "-o", "yaml",
    ])
    have = subprocess.run(k + ["get", "secret", "mcp-auth", "-n", ns], capture_output=True, text=True)
    if have.returncode != 0:
        _apply_secret(k, [
            "create", "secret", "generic", "mcp-auth", "-n", ns,
            f"--from-literal=read={secrets.token_urlsafe(32)}",
            f"--from-literal=write={secrets.token_urlsafe(32)}",
            f"--from-literal=vcf-read={secrets.token_urlsafe(32)}",
            f"--from-literal=vcf-admin={secrets.token_urlsafe(32)}",
            "--dry-run=client", "-o", "yaml",
        ])
    controller = subprocess.run(
        k + ["get", "cm", "avi-k8s-config", "-n", "avi-system", "-o", "jsonpath={.data.controllerAddress}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    user = base64.b64decode(subprocess.run(
        k + ["get", "secret", "avi-secret", "-n", "avi-system", "-o", "jsonpath={.data.username}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()).decode()
    password = base64.b64decode(subprocess.run(
        k + ["get", "secret", "avi-secret", "-n", "avi-system", "-o", "jsonpath={.data.password}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()).decode()
    _apply_secret(k, [
        "create", "secret", "generic", "avi-goad", "-n", ns,
        f"--from-literal=controller={controller}",
        f"--from-literal=username={user}",
        f"--from-literal=password={password}",
        "--dry-run=client", "-o", "yaml",
    ])


def main() -> None:
    for name in REQUIRED:
        need(name)
    ensure_admin_password()
    os.environ.setdefault("PROMETHEUS_URL", "http://prometheus.example.invalid")
    kube = os.environ.get("KUBECONFIG", "").strip()
    if not kube:
        raise SystemExit("KUBECONFIG is unset")
    k = ["kubectl", "--kubeconfig", kube]

    rendered = subprocess.run(
        ["kubectl", "kustomize", "--load-restrictor", "LoadRestrictionsNone", str(ROOT / "store")],
        capture_output=True, text=True,
    )
    if rendered.returncode != 0:
        raise SystemExit(rendered.stderr.strip() or "kustomize failed")
    run(k + ["apply", "-f", "-"], input_text=fill(rendered.stdout))

    secret = subprocess.run(
        k + ["create", "secret", "generic", "store-db", "-n", "metal-music-store", f"--from-literal=password={store_password()}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    run(k + ["apply", "-f", "-"], input_text=secret.stdout)
    chat = subprocess.run(
        k + ["create", "secret", "generic", "metal-oracle-model", "-n", "metal-music-store",
             f"--from-literal=base-url={need('QWEN_BASE_URL')}",
             f"--from-literal=api-key={need('QWEN_API_KEY')}",
             "--from-literal=model=qwen",
             "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    run(k + ["apply", "-f", "-"], input_text=chat.stdout)

    zammad = fill((ROOT / "incident-tools" / "zammad.yaml").read_text())
    grafana = fill((ROOT / "incident-tools" / "grafana.yaml").read_text())
    run(k + ["apply", "-f", "-"], input_text=zammad)
    run(k + ["apply", "-f", "-"], input_text=grafana)
    zenv = "\n".join([
        "POSTGRESQL_HOST=zammad-postgresql",
        "POSTGRESQL_PORT=5432",
        "POSTGRESQL_USER=zammad",
        f"POSTGRESQL_PASS={need('ZAMMAD_DB_PASSWORD')}",
        "POSTGRESQL_DB=zammad_production",
        "REDIS_URL=redis://zammad-redis:6379",
        "MEMCACHE_SERVERS=zammad-memcached:11211",
        "ELASTICSEARCH_ENABLED=false",
        "POSTGRESQL_DB_CREATE=false",
        "ZAMMAD_RAILSSERVER_HOST=127.0.0.1",
        "ZAMMAD_RAILSSERVER_PORT=3000",
        "ZAMMAD_WEBSOCKET_HOST=127.0.0.1",
        "ZAMMAD_WEBSOCKET_PORT=6042",
        "NGINX_PORT=8080",
        "RAILS_ENV=production",
        "RAILS_LOG_TO_STDOUT=true",
        f"ZAMMAD_FQDN={need('ZAMMAD_HOST')}",
        "ZAMMAD_HTTP_TYPE=https",
        f"AUTOWIZARD_JSON={wizard_b64()}",
    ]) + "\n"
    # Build the secret from an env file. The file is removed after apply.
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        handle.write(zenv)
        env_path = handle.name
    try:
        built = subprocess.run(
            k + ["create", "secret", "generic", "zammad-env", "-n", "incident-tools", f"--from-env-file={env_path}", "--dry-run=client", "-o", "yaml"],
            capture_output=True, text=True, check=True,
        )
        run(k + ["apply", "-f", "-"], input_text=built.stdout)
    finally:
        os.unlink(env_path)
    gsecret = subprocess.run(
        k + ["create", "secret", "generic", "grafana-admin", "-n", "incident-tools", f"--from-literal=password={need('GRAFANA_ADMIN_PASSWORD')}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    run(k + ["apply", "-f", "-"], input_text=gsecret.stdout)

    run(k + ["apply", "-f", str(ROOT / "agents" / "workloads.yaml")])
    idle = subprocess.run(
        k + ["create", "configmap", "agent-idle", "-n", "metal-music-app-agentic-system", f"--from-file=idle.py={ROOT / 'agents' / 'idle.py'}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    run(k + ["apply", "-f", "-"], input_text=idle.stdout)
    scrub = subprocess.run(
        k + ["create", "configmap", "pii-scrub", "-n", "metal-music-app-agentic-system", f"--from-file=scrub.py={ROOT / 'pii' / 'scrub.py'}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    run(k + ["apply", "-f", "-"], input_text=scrub.stdout)
    for name in (
        "incident-response-agent",
        "lb-diagnostic-agent",
        "k8s-diagnostic-agent",
        "vcf-diagnostic-agent",
        "pii-scrub",
    ):
        subprocess.run(k + ["rollout", "restart", "deployment", name, "-n", "metal-music-app-agentic-system"], capture_output=True, text=True)

    ensure_mcp_secrets(k)
    run(k + ["apply", "-f", str(ROOT / "mcp" / "workloads.yaml")])
    for name, folder in (("mcp-k8s", ROOT / "mcp" / "k8s"), ("mcp-avi", ROOT / "mcp" / "avi")):
        built = subprocess.run(
            k + ["create", "configmap", name, "-n", "metal-music-app-agentic-system", f"--from-file={folder}", "--dry-run=client", "-o", "yaml"],
            capture_output=True, text=True, check=True,
        )
        run(k + ["apply", "-f", "-"], input_text=built.stdout)
    tar_path = Path(tempfile.mkdtemp()) / "package.tar"
    with tarfile.open(tar_path, "w") as archive:
        archive.add(ROOT / "mcp" / "vcf" / "vcf_mcp", arcname="vcf_mcp")
    vcf = subprocess.run(
        k + ["create", "configmap", "mcp-vcf", "-n", "metal-music-app-agentic-system", f"--from-file=package.tar={tar_path}", "--dry-run=client", "-o", "yaml"],
        capture_output=True, text=True, check=True,
    )
    # Server-side apply: a client-side apply stores the whole tar in
    # last-applied-configuration, and that annotation exceeds 256Ki.
    run(k + ["apply", "--server-side", "--force-conflicts", "-f", "-"], input_text=vcf.stdout)
    for name in ("goad-k8s-mcp", "goad-avi-mcp", "goad-vcf-mcp"):
        subprocess.run(k + ["rollout", "restart", "deployment", name, "-n", "metal-music-app-agentic-system"], capture_output=True, text=True)

    image = os.environ.get("CLM_IMAGE", "").strip()
    if image:
        run(k + ["apply", "-f", "-"], input_text=fill((ROOT / "clm" / "clm.yaml").read_text().replace("${CLM_IMAGE}", image)))
        print("clm applied")
    else:
        print("clm skipped: CLM_IMAGE is empty")
    print("applied")


if __name__ == "__main__":
    main()
