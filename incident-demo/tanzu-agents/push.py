#!/usr/bin/env python3
"""Push the Metal Music agents and MCP doors into org Goad.

Space metal-music-app-agentic-system on the Red Lab Tanzu Platform.
The model is Goad Private AI (env QWEN_BASE_URL). This script does not
create an ai-models service and does not read a DGX plan.

Secrets are read from mode-600 files and set with the cf API.
Nothing secret is printed.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORG = "Goad"
SPACE = "metal-music-app-agentic-system"
DOMAIN = os.environ.get("TANZU_APPS_DOMAIN", "apps.tp.gpu.set.lab")
CF_HOME = Path(os.environ.get("CF_HOME", "/tmp/redlab-cf-goad"))
HOSTS = Path.home() / ".cache" / "redlab-tpcf" / "hosts"
SDK = Path.home() / ".cache" / "redlab-tpcf" / "agentminder-sdk" / "4.1.0.1578" / "site-packages"
SIDECAR_SRC = Path("/tmp/the-goad-work/incident/agents/sidecar")

AGENTS = {
    "incident-response-agent": ("chat.py", "incident-response"),
    "lb-diagnostic-agent": ("diagnose.py", "lb-diagnostic"),
    "k8s-diagnostic-agent": ("diagnose.py", "k8s-diagnostic"),
    "vcf-diagnostic-agent": ("diagnose.py", "vcf-diagnostic"),
}
DOORS = ("lb-diagnostic-agent", "k8s-diagnostic-agent", "vcf-diagnostic-agent")
ROLE = {
    "lb-diagnostic-agent": "lb_diagnostic_agent",
    "k8s-diagnostic-agent": "k8s_diagnostic_agent",
    "vcf-diagnostic-agent": "vcf_diagnostic_agent",
}
CLIENT = {
    "lb-diagnostic-agent": "py-goad-lb",
    "k8s-diagnostic-agent": "py-goad-k8s",
    "vcf-diagnostic-agent": "py-goad-vcf",
}
SERVER = {
    "lb-diagnostic-agent": "goad-avi-mcp",
    "k8s-diagnostic-agent": "goad-k8s-mcp",
    "vcf-diagnostic-agent": "goad-vcf-mcp",
}


def cf(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [
        "bwrap",
        "--bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--ro-bind",
        str(HOSTS),
        "/etc/hosts",
        "--",
        "cf",
        *args,
    ]
    env = os.environ.copy()
    env["CF_HOME"] = str(CF_HOME)
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env)
    if check and proc.returncode != 0:
        tail = (proc.stdout + proc.stderr)[-1500:]
        raise SystemExit(f"cf {args[0]} failed\n{tail}")
    return proc


def cf_curl(path: str, method: str = "GET", body: dict | None = None) -> dict:
    cmd = ["curl", path, "-X", method]
    if body is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(body)])
    proc = cf(*cmd)
    doc = json.loads(proc.stdout) if proc.stdout.strip() else {}
    if isinstance(doc, dict) and doc.get("errors"):
        raise SystemExit(f"cf curl {method} {path.split('?')[0]} failed")
    return doc


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip("'").strip('"')
    return out


def space_guid() -> str:
    org = (cf_curl(f"/v3/organizations?names={ORG}").get("resources") or [{}])[0].get("guid")
    rows = cf_curl(f"/v3/spaces?names={SPACE}&organization_guids={org}").get("resources") or []
    if not rows:
        raise SystemExit("missing space")
    return rows[0]["guid"]


def app_guid(name: str) -> str:
    rows = cf_curl(f"/v3/apps?names={name}&space_guids={space_guid()}").get("resources") or []
    if not rows:
        raise SystemExit(f"missing app {name}")
    return rows[0]["guid"]


def set_env(name: str, updates: dict) -> None:
    updates = {k: v for k, v in updates.items() if v}
    if not updates:
        return
    cf_curl(f"/v3/apps/{app_guid(name)}/environment_variables", "PATCH", {"var": updates})
    print("env", name, "keys", ",".join(sorted(updates)), flush=True)


def ups(name: str, credentials: dict, tags: list[str] | None = None) -> None:
    space = space_guid()
    body: dict = {"credentials": credentials}
    if tags is not None:
        body["tags"] = tags
    rows = cf_curl(f"/v3/service_instances?names={name}&space_guids={space}").get("resources") or []
    if rows:
        cf_curl(f"/v3/service_instances/{rows[0]['guid']}", "PATCH", body)
    else:
        body.update(
            {
                "type": "user-provided",
                "name": name,
                "relationships": {"space": {"data": {"guid": space}}},
            }
        )
        cf_curl("/v3/service_instances", "POST", body)
    print("service", name, "ready", flush=True)


def bind(app: str, service: str) -> None:
    proc = cf("bind-service", app, service, check=False)
    if proc.returncode != 0 and "already bound" not in (proc.stdout + proc.stderr):
        raise SystemExit(f"bind {service} to {app} failed")


def write_manifest(app: dict) -> Path:
    path = Path(tempfile.mkdtemp(prefix="goad-manifest-")) / "manifest.yml"
    text = json.dumps({"applications": [app]}, indent=2)
    text = text.replace("${TANZU_APPS_DOMAIN}", DOMAIN)
    path.write_text(text + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def push(app: dict) -> None:
    print("pushing", app["name"], flush=True)
    manifest = write_manifest(app)
    proc = cf("push", app["name"], "-f", str(manifest), "--no-start")
    manifest.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise SystemExit(f"push {app['name']} failed")
    print("pushed", app["name"], flush=True)


def ignore_junk(_dir, names):
    return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]


def stage_agent(name: str, entry: str, skill: str) -> Path:
    """Stage a Tanzu agent buildpack app.

    The buildpack is the Pydantic agent. It reads AGENTS.md and
    .agents/skills. The old diagnose.py and chat.py files stay out of
    this tree so they cannot become the start command.
    """
    dest = Path(tempfile.mkdtemp(prefix=f"{name}-"))
    agents = ROOT / "agents"
    skill_name = ROLE.get(name, "incident_response_agent")
    role = agents / "roles" / f"{name}.md"
    if not role.is_file():
        raise SystemExit(f"missing role {role}")
    (dest / "AGENTS.md").write_text(role.read_text(encoding="utf-8"), encoding="utf-8")
    target = dest / ".agents" / "skills" / skill_name
    target.mkdir(parents=True)
    shutil.copy(agents / skill / "skills" / "SKILL.md", target / "SKILL.md")
    schema = agents / "schema" / "findings.schema.json"
    if schema.is_file():
        shutil.copy(schema, target / "findings.schema.json")
    (dest / "runtime.txt").write_text("python-3.12.x\n", encoding="utf-8")
    # The buildpack only installs the app root requirements. Diagnostic
    # agents also start the sidecar, which imports the staged SDK.
    deps = "PyJWT[crypto]>=2.8\n"
    if name in DOORS:
        deps += "uvicorn>=0.30\nhttpx>=0.27\nanyio>=4\ncryptography>=42\nPyYAML>=6\n"
    (dest / "requirements.txt").write_text(deps, encoding="utf-8")
    if name in DOORS:
        side = dest / "sidecar"
        side.mkdir()
        for filename in ("run-sidecar.sh", "mcp_bridge.py"):
            shutil.copy(SIDECAR_SRC / filename, side / filename)
        shutil.copytree(SDK, side / "site-packages", ignore=ignore_junk)
        (side / "requirements.txt").write_text(
            "uvicorn>=0.30\nhttpx>=0.27\nanyio>=4\ncryptography>=42\nPyJWT[crypto]>=2.8\n",
            encoding="utf-8",
        )
    stage_model_trust(dest)
    return dest


def stage_model_trust(dest: Path) -> None:
    """Let the agent trust the Goad model ingress.

    The ingress certificate is named pais-ingress-default and is signed
    by that service's own CA. The agent client checks the name. The
    address stays the Goad ingress. This does not point at the pais org.
    """
    trust = Path(__file__).resolve().parent / "trust"
    ca = trust / "pais-root.pem"
    proxy = trust / "model_proxy.py"
    if not ca.is_file() or not proxy.is_file():
        raise SystemExit("missing model trust files")
    shutil.copy(ca, dest / "pais-root.pem")
    shutil.copy(proxy, dest / "model_proxy.py")
    (dest / ".profile").write_text(
        """# The agent HTTP client uses SSL_CERT_FILE when it is set.
# The model itself is reached through the local proxy, because this
# container cannot edit /etc/hosts and the certificate name is not the address.
base="${SSL_CERT_FILE:-/etc/ssl/certs/ca-certificates.crt}"
if [ -r "$base" ] && [ -r /home/vcap/app/pais-root.pem ]; then
  cat "$base" /home/vcap/app/pais-root.pem > /home/vcap/app/trust-bundle.pem
  export SSL_CERT_FILE=/home/vcap/app/trust-bundle.pem
  echo 'trust: model CA added' >&2
else
  echo 'trust: model CA was not added' >&2
fi
python3 - << 'PY'
import socket, subprocess
s = socket.socket()
s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", 8765))
except Exception:
    subprocess.Popen(
        ["python3", "/home/vcap/app/model_proxy.py"],
        stdout=open("/home/vcap/app/model-proxy.log", "ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print("trust: model proxy started", flush=True)
else:
    print("trust: model proxy already listening", flush=True)
finally:
    s.close()
PY
""",
        encoding="utf-8",
    )


def stage_tree(src: Path, names: list[str]) -> Path:
    dest = Path(tempfile.mkdtemp(prefix=src.name + "-"))
    for name in names:
        item = src / name
        if item.is_dir():
            shutil.copytree(item, dest / name, ignore=ignore_junk)
        elif item.is_file():
            shutil.copy(item, dest / name)
    (dest / "runtime.txt").write_text("python-3.12.x\n", encoding="utf-8")
    return dest


def base_app(name: str, path: Path, memory: str, disk: str, command: str, buildpacks: list[str], extra: dict | None = None) -> dict:
    spec = {
        "name": name,
        "path": str(path),
        "memory": memory,
        "disk_quota": disk,
        "instances": 1,
        "timeout": 180,
        "health-check-type": "http",
        "health-check-http-endpoint": "/health",
        "health-check-invocation-timeout": 60,
        "command": command,
        "buildpacks": buildpacks,
        "routes": [{"route": f"{name}.{DOMAIN}"}],
    }
    if extra:
        spec.update(extra)
    return spec


def update_resource_routes() -> None:
    """Point the existing Goad resource servers at the new MCP routes."""
    token = os.environ.get("AM_MCP_TOKEN", "").strip()
    if not token:
        print("agentminder routes not updated: AM_MCP_TOKEN unset", flush=True)
        return
    clients = json.loads(Path("/tmp/goad-am-clients.json").read_text(encoding="utf-8"))
    host = "agentminder.goad.gpu.set.lab"
    ip = "10.47.7.82"
    routes = {
        "goad-k8s-mcp": f"https://metal-k8s-mcp.{DOMAIN}/mcp",
        "goad-avi-mcp": f"https://metal-avi-mcp.{DOMAIN}/mcp",
        "goad-vcf-mcp": f"https://metal-vcf-mcp.{DOMAIN}/mcp",
    }
    ctx = ssl._create_unverified_context()

    def call(tool: str, arguments: dict) -> dict:
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}
        ).encode()
        req = urllib.request.Request(
            f"https://{host}/default/mcp",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Authorization": "Bearer " + token,
                "x-tenant-name": "default",
                "Host": host,
            },
        )

        class Handler(urllib.request.HTTPSHandler):
            def https_open(self, request):
                def mk(h, timeout=None, source_address=None):
                    class Conn(urllib.request.http.client.HTTPSConnection):
                        def connect(self):
                            sock = socket.create_connection((ip, 443), self.timeout)
                            self.sock = ctx.wrap_socket(sock, server_hostname=host)

                    return Conn(h, timeout=timeout, context=ctx)

                return self.do_open(mk, request)

        try:
            with urllib.request.build_opener(Handler()).open(req, timeout=60) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            print("agentminder", tool, "HTTP", exc.code, flush=True)
            return {}
        text = raw
        if "data:" in raw:
            for line in raw.splitlines():
                if line.startswith("data:"):
                    text = line[5:].strip()
                    break
        doc = json.loads(text)
        result = doc.get("result") or {}
        content = result.get("content") if isinstance(result, dict) else None
        parsed = content[0].get("text") if isinstance(content, list) and content else doc
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                parsed = {"raw": parsed[:120]}
        return parsed if isinstance(parsed, dict) else {}

    for name, backend in routes.items():
        app_id = clients["servers"][name]["appId"]
        result = call(
            "update_app",
            {
                "id": app_id,
                "request": json.dumps(
                    {
                        "mcpServerEndpoint": backend,
                        "secondaryAudiences": [backend],
                        "mcpIgnoreSslValidation": True,
                    }
                ),
            },
        )
        if result:
            print("agentminder route", name, "updated", flush=True)
        else:
            print("agentminder route", name, "not updated", flush=True)


def main() -> None:
    if not CF_HOME.is_dir() or not HOSTS.is_file():
        raise SystemExit("cf home or hosts file missing")
    cf("target", "-o", ORG, "-s", SPACE)
    demo = load_env(Path("/tmp/goad-demo.env"))
    clients = json.loads(Path("/tmp/goad-am-clients.json").read_text(encoding="utf-8"))
    workers = os.environ.get(
        "STORE_WORKER_VMS",
        "music-store-workers-6xtl4-wnr4j-8n8n5,music-store-workers-6xtl4-wnr4j-gjwhn",
    )
    connect = {
        "ZAMMAD_CONNECT_IP": "10.47.7.83",
        "STORE_CONNECT_IP": "10.47.7.68",
        "GRAFANA_CONNECT_IP": "10.47.7.84",
        "AGENTMINDER_CONNECT_IP": "10.47.7.82",
    }
    qwen = {
        "QWEN_BASE_URL": demo.get("QWEN_BASE_URL", ""),
        "QWEN_API_KEY": demo.get("QWEN_API_KEY", ""),
        "QWEN_MODEL": "qwen",
    }

    # Doors first so the agents have somewhere to call.
    k8s = stage_tree(ROOT / "mcp" / "k8s", ["k8s_mcp.py", "mcp_http.py", "idsp_bearer.py"])
    (k8s / "requirements.txt").write_text("PyJWT[crypto]>=2.8\n", encoding="utf-8")
    push(base_app("metal-k8s-mcp", k8s, "256M", "1G", "python k8s_mcp.py", ["python_buildpack"]))

    avi = stage_tree(ROOT / "mcp" / "avi", ["server.py", "client.py", "mcp_http.py", "idsp_bearer.py"])
    (avi / "requirements.txt").write_text("PyJWT[crypto]>=2.8\n", encoding="utf-8")
    push(base_app("metal-avi-mcp", avi, "256M", "512M", "python server.py", ["python_buildpack"]))

    vcf = stage_tree(ROOT / "mcp" / "vcf", ["vcf_mcp", "specs"])
    (vcf / "requirements.txt").write_text(
        "mcp>=2.0.0\nhttpx>=0.27\nPyYAML>=6\nuvicorn>=0.30\nstarlette>=0.37\nPyJWT[crypto]>=2.8\n",
        encoding="utf-8",
    )
    (vcf / "hosts.json").write_text('{"hosts":{}}\n', encoding="utf-8")
    push(
        base_app(
            "metal-vcf-mcp",
            vcf,
            "1G",
            "2G",
            "python -m vcf_mcp serve-http",
            ["python_buildpack"],
            {"health-check-invocation-timeout": 120},
        )
    )

    pii = stage_tree(ROOT / "pii", ["scrub.py"])
    push(base_app("pii-scrub", pii, "256M", "512M", "python scrub.py", ["python_buildpack"]))

    live = stage_tree(ROOT / "agents" / "orchestrator", ["harness.py"])
    push(base_app("metal-incident-live", live, "512M", "1G", "python harness.py", ["python_buildpack"]))

    for name, (entry, skill) in AGENTS.items():
        extra = {}
        if name in DOORS:
            extra["sidecars"] = [
                {
                    "name": "agentminder-sdk",
                    "process_types": ["web"],
                    "command": "bash sidecar/run-sidecar.sh",
                    "memory": "128M",
                }
            ]
        packs = ["python_buildpack", "agent_buildpack"]
        spec = base_app(name, stage_agent(name, entry, skill), "512M", "1G", "", packs, extra)
        spec.pop("command", None)
        push(spec)

    issuer = "https://agentminder.goad.gpu.set.lab/default"
    mcp_read = os.environ.get("MCP_READ_TOKEN", "").strip() or os.urandom(24).hex()
    mcp_write = os.environ.get("MCP_WRITE_TOKEN", "").strip() or os.urandom(24).hex()
    if mcp_read == mcp_write:
        mcp_write = os.urandom(24).hex()
    set_env(
        "metal-k8s-mcp",
        {
            "IDSP_ISSUER": issuer,
            "IDSP_TLS_VERIFY": "0",
            "AGENTMINDER_CONNECT_IP": connect["AGENTMINDER_CONNECT_IP"],
            "MCP_RESOURCE_URL": f"https://metal-k8s-mcp.{DOMAIN}/mcp",
            "MCP_READ_TOKEN": mcp_read,
            "MCP_WRITE_TOKEN": mcp_write,
            "K8S_API_SERVER": os.environ.get("K8S_API_SERVER", ""),
            "K8S_TOKEN": os.environ.get("K8S_TOKEN", ""),
            "K8S_NAMESPACE": "music-store",
            "K8S_API_TIMEOUT": "40",
        },
    )
    set_env(
        "metal-avi-mcp",
        {
            "IDSP_ISSUER": issuer,
            "IDSP_TLS_VERIFY": "0",
            "AGENTMINDER_CONNECT_IP": connect["AGENTMINDER_CONNECT_IP"],
            "MCP_RESOURCE_URL": f"https://metal-avi-mcp.{DOMAIN}/mcp",
            "MCP_READ_TOKEN": mcp_read,
            "MCP_WRITE_TOKEN": mcp_write,
            "AVI_CONTROLLER": os.environ.get("AVI_CONTROLLER", ""),
            "AVI_USERNAME": os.environ.get("AVI_USERNAME", ""),
            "AVI_PASSWORD": os.environ.get("AVI_PASSWORD", ""),
            "AVI_TENANT": os.environ.get("AVI_TENANT") or "goad",
        },
    )
    set_env(
        "metal-vcf-mcp",
        {
            "IDSP_ISSUER": issuer,
            "AGENTMINDER_CONNECT_IP": connect["AGENTMINDER_CONNECT_IP"],
            "VCF_MCP_HOSTS_FILE": "/home/vcap/app/hosts.json",
            "VCF_MCP_SPEC_DIR": "/home/vcap/app/specs",
            "VCF_ALLOWED_HOSTS": f"metal-vcf-mcp.{DOMAIN}",
            "VCF_MCP_RESOURCE_URL": f"https://metal-vcf-mcp.{DOMAIN}/mcp",
            "VCF_MCP_VERIFY_TLS": "0",
            "VCF_MCP_OAUTH_TLS_VERIFY": "0",
            "VCF_MCP_OAUTH_ISSUER": issuer,
            "VCF_DISK_LATENCY_REPLAY": "on",
            "PYTHONPATH": "/home/vcap/app",
            "PYTHONUNBUFFERED": "1",
        },
    )
    set_env(
        "metal-incident-live",
        {
            **qwen,
            **connect,
            "STORE_URL": demo.get("STORE_URL", ""),
            "GRAFANA_URL": os.environ.get("GRAFANA_URL", "http://grafana.goad.gpu.set.lab"),
            "GRAFANA_ADMIN_PASSWORD": os.environ.get("GRAFANA_ADMIN_PASSWORD") or demo.get("GRAFANA_ADMIN_PASSWORD", ""),
            "LB_AGENT_URL": "http://lb-diagnostic-agent.apps.internal:8080/api/chat",
            "K8S_AGENT_URL": "http://k8s-diagnostic-agent.apps.internal:8080/api/chat",
            "VCF_AGENT_URL": "http://vcf-diagnostic-agent.apps.internal:8080/api/chat",
            "STORE_WORKER_VMS": workers,
        },
    )
    set_env(
        "incident-response-agent",
        {
            "ZAMMAD_URL": demo.get("ZAMMAD_URL", ""),
            "ZAMMAD_TOKEN": demo.get("ZAMMAD_TOKEN", ""),
            "ZAMMAD_CONNECT_IP": connect["ZAMMAD_CONNECT_IP"],
            "ORCHESTRATOR_URL": "http://metal-incident-live.apps.internal:8080/run",
        },
    )
    token = os.urandom(32).hex()
    for name in DOORS:
        client = clients["clients"][CLIENT[name]]
        gateway = clients["servers"][SERVER[name]]["gateway"]
        door = "avi" if "lb" in name else "k8s" if "k8s" in name else "vcf"
        set_env(
            name,
            {
                **qwen,
                "AGENT_ROLE": ROLE[name],
                "STORE_WORKER_VMS": workers,
                "AM_TOKEN_URL": issuer + "/oauth2/v1/token",
                "AM_CLIENT_ID": client.get("clientId", ""),
                "AM_CLIENT_SECRET": client.get("secret", ""),
                "AM_GATEWAY": gateway,
                "AGENTMINDER_CONNECT_IP": connect["AGENTMINDER_CONNECT_IP"],
                "AGENTMINDER_SIDECAR_TOKEN": token,
                "AGENTMINDER_IDSP_URL": issuer,
                "AGENTMINDER_SIDECAR_AGENT_CLIENT_ID": client.get("clientId", ""),
                "AGENTMINDER_SIDECAR_AGENT_CLIENT_SECRET": client.get("secret", ""),
                "AGENTMINDER_ORCHESTRATOR_CLIENT_ID": client.get("clientId", ""),
                "AGENTMINDER_ORCHESTRATOR_CLIENT_SECRET": client.get("secret", ""),
                "AGENTMINDER_VERIFY_SSL": "false",
                "AGENTMINDER_SIDECAR_RESOURCE_0_NAME": door,
                "AGENTMINDER_SIDECAR_RESOURCE_0_URL": gateway,
                "AGENTMINDER_SIDECAR_RESOURCE_0_AUDIENCE": gateway,
            },
        )

    ups(
        "k8s-mcp-cluster",
        {
            "server": os.environ.get("K8S_API_SERVER", ""),
            "token": os.environ.get("K8S_TOKEN", ""),
            "namespace": "music-store",
        },
    )
    ups(
        "sc-incident-response-agent-orch",
        {"url": f"https://metal-incident-live.{DOMAIN}/mcp"},
        ["mcp-server"],
    )
    for name, door in (
        ("lb-diagnostic-agent", "avi"),
        ("k8s-diagnostic-agent", "k8s"),
        ("vcf-diagnostic-agent", "vcf"),
    ):
        ups(
            f"sc-{name}-{door}",
            {"url": f"http://127.0.0.1:8181/mcp?resource={door}", "api_key": token, "auth_type": "bearer"},
            ["mcp-server"],
        )

    # apps.internal stays empty until the route is mapped. A network
    # policy alone does not publish the container address.
    for name in ("metal-incident-live", *DOORS):
        cf("map-route", name, "apps.internal", "--hostname", name, check=False)
    cf(
        "add-network-policy",
        "incident-response-agent",
        "metal-incident-live",
        "--protocol",
        "tcp",
        "--port",
        "8080",
        check=False,
    )
    for name in DOORS:
        cf(
            "add-network-policy",
            "metal-incident-live",
            name,
            "--protocol",
            "tcp",
            "--port",
            "8080",
            check=False,
        )
    bind("incident-response-agent", "sc-incident-response-agent-orch")
    bind("metal-k8s-mcp", "k8s-mcp-cluster")
    for name, door in (
        ("lb-diagnostic-agent", "avi"),
        ("k8s-diagnostic-agent", "k8s"),
        ("vcf-diagnostic-agent", "vcf"),
    ):
        bind(name, f"sc-{name}-{door}")
    for name in (
        "metal-k8s-mcp",
        "metal-avi-mcp",
        "metal-vcf-mcp",
        "pii-scrub",
        "metal-incident-live",
        *AGENTS,
    ):
        cf("start", name)
        print("started", name, flush=True)
    update_resource_routes()
    print("push complete", flush=True)


def app_env(name: str) -> dict:
    return dict(cf_curl(f"/v3/apps/{app_guid(name)}/environment_variables").get("var") or {})


def clear_command(name: str) -> None:
    """Drop a python chat.py / diagnose.py override so the droplet command runs."""
    proc = (cf_curl(f"/v3/apps/{app_guid(name)}/processes").get("resources") or [{}])[0]
    guid = proc.get("guid")
    if not guid:
        raise SystemExit(f"no process for {name}")
    cf_curl(f"/v3/processes/{guid}", "PATCH", {"command": None})
    current = cf_curl(f"/v3/processes/{guid}").get("command")
    print("command", name, current or "buildpack-default", flush=True)


def bind_goad_model() -> None:
    """User-provided model binding for the agent buildpack.

    The marketplace chat plan is not the Goad qwen. Credentials are copied
    from an app env that already holds them. Values are not printed.
    """
    src = app_env("lb-diagnostic-agent")
    base = (src.get("QWEN_BASE_URL") or "").rstrip("/")
    key = src.get("QWEN_API_KEY") or ""
    model = src.get("QWEN_MODEL") or "qwen"
    if not base or not key:
        raise SystemExit("qwen env missing on lb-diagnostic-agent")
    if "pais.gpu" in base or "/pais" in base:
        raise SystemExit("refusing the pais model endpoint")
    if "10.47.7.73" not in base and "127.0.0.1:8765" not in base:
        raise SystemExit("refusing a model endpoint that is not the Goad ingress")
    # The agent appends /openai/v1 to endpoint.api_base. The local proxy
    # accepts that path and forwards it to the Goad ingress.
    proxy = "http://127.0.0.1:8765"
    chat_base = proxy + "/api/v1/compatibility/openai/v1"
    endpoint_root = proxy + "/api/v1/compatibility"
    print("model binding", "goad", flush=True)
    ups(
        "goad-qwen",
        {
            "api_base": chat_base,
            "api_key": key,
            "model_name": model,
            "model_capabilities": ["chat", "tools"],
            "wire_format": "openai",
            "endpoint": {
                "api_base": endpoint_root,
                "openai_api_base": chat_base,
                "api_key": key,
                "config_url": f"https://metal-incident-live.{DOMAIN}/config/v1/endpoint",
                "name": model,
            },
        },
        ["tanzu-ai-models", "ai-models", "genai", "llm"],
    )


def push_agents() -> None:
    """Restage the four agents onto agent_buildpack and the orchestrator tools.

    Does not restage the MCP doors and does not rotate their tokens.
    """
    if not CF_HOME.is_dir() or not HOSTS.is_file():
        raise SystemExit("cf home or hosts file missing")
    cf("target", "-o", ORG, "-s", SPACE)
    bind_goad_model()
    for name, (entry, skill) in AGENTS.items():
        extra: dict = {"env": {"TANZU_AGENT_ENABLE_DEBUG_UI": "true"}}
        if name in DOORS:
            extra["sidecars"] = [
                {
                    "name": "agentminder-sdk",
                    "process_types": ["web"],
                    "command": "bash sidecar/run-sidecar.sh",
                    "memory": "128M",
                }
            ]
        spec = base_app(name, stage_agent(name, entry, skill), "512M", "1G", "", ["python_buildpack", "agent_buildpack"], extra)
        spec.pop("command", None)
        push(spec)
        clear_command(name)
        bind(name, "goad-qwen")
    live = stage_tree(ROOT / "agents" / "orchestrator", ["harness.py"])
    push(base_app("metal-incident-live", live, "512M", "1G", "python harness.py", ["python_buildpack"]))
    zammad = app_env("incident-response-agent")
    set_env(
        "metal-incident-live",
        {
            "ZAMMAD_URL": zammad.get("ZAMMAD_URL", ""),
            "ZAMMAD_TOKEN": zammad.get("ZAMMAD_TOKEN", ""),
            "ZAMMAD_CONNECT_IP": zammad.get("ZAMMAD_CONNECT_IP", ""),
        },
    )
    for name in (*AGENTS, "metal-incident-live"):
        cf("start", name)
        print("started", name, flush=True)
    print("agent framework push complete", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "agents":
        push_agents()
    else:
        main()
