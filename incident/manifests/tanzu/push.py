#!/usr/bin/env python3
"""Push the Metal Music agents and MCP doors into one Tanzu space.

VCFA org Goad. Space comes from GOAD_VCFA_SPACE and stays blank until the Captain approves PLAN.md.

    python3 manifests/tanzu/push.py mcp [k8s|vcf|avi]          # MCP doors
    python3 manifests/tanzu/push.py agents [<agent app> ...]   # the agents
    python3 manifests/tanzu/push.py all

Staging on this foundation can take ten minutes or more per app. Doors
and agents may be pushed one at a time in parallel shells.

Buildpacks and sizes copy the earlier demos. MCP doors are
python_buildpack with HTTP /health, like k8s-mcp and vcf-mcp. Agents are
python_buildpack then agent_buildpack with the agentminder-sdk sidecar,
like infrademo-agent.

The AgentMinder sidecar exits when the issuer does not answer, and that
crashes the whole instance. When the token endpoint is not 200 or 400,
agents are uploaded, bound, and staged, then left stopped. Start them
with `cf start <app>` once the issuer answers and the grants exist.

Secrets are read from ~/secrets or copied app to app with the cf API.
Nothing secret is printed or written into this repo.
"""

from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORG = "Goad"
SPACE = os.environ.get("GOAD_VCFA_SPACE", "")
DOMAIN = "${TANZU_APPS_DOMAIN}"
ISSUER = "https://${AGENTMINDER_HOST}/default"
TOKEN_URL = f"{ISSUER}/oauth2/v1/token"
SECRETS = Path.home() / "secrets"
SIDECARS = SECRETS / "metal-music-sidecars.json"
AGENT_CLIENTS = SECRETS / "metal-music-agents.json"

AGENTS = ROOT / "agents"
AVI_SRC = ROOT / "avi-mcp"
K8S_SRC = Path(os.environ.get("K8S_MCP_SRC", str(ROOT / "mcp" / "k8s")))
VCF_SRC = Path(os.environ.get("VCF_MCP_SRC", str(ROOT / "mcp" / "vcf")))
VCF_HOSTS = Path(os.environ.get("VCF_MCP_HOSTS_FILE", Path.home() / ".config" / "vcf-mcp" / "hosts.json"))

DOORS = {
    "k8s": "metal-k8s-mcp",
    "vcf": "metal-vcf-mcp",
    "avi": "metal-avi-mcp",
}
LIVE_APP = "metal-incident-live"
LIVE_SECRETS = SECRETS / "metal-incident-live.env"
ORCH_SERVICE = "sc-incident-response-agent-orch"

ROLES = {
    # No Kubernetes or VCF door. Zammad, Jev, and the domain agents only.
    "incident-response-agent": [],
    "lb-diagnostic-agent": ["avi"],
    "k8s-diagnostic-agent": ["k8s"],
    "vcf-diagnostic-agent": ["vcf"],
}

# AgentMinder AI Gateway route of resource server avi-mcp. The company
# brain's metal_music_grants.py creates that server and prints this URL.
AVI_GATEWAY = (
    "https://${AGENTMINDER_HOST}/default/aigateway/v1/mcp/"
    "NTBkYWY1MWItZDBlZC00MDUxLWFhM2YtNDQ1MzYwZWI1Y2Uz"
)
SKILLS = ROOT / "skills"
SCHEMA = SKILLS / "schema" / "findings.schema.json"

LLM_SERVICE = "spark1-llm"
LLM_OFFERING = "ai-models"
LLM_PLAN = "spark1-qwen-122b"


def cf(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ cf", " ".join(args[:4]), flush=True)
    proc = subprocess.run(["cf", *args], text=True, capture_output=True)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        raise SystemExit(f"cf {args[0]} failed")
    return proc


def cf_curl(path: str, method: str = "GET", body: dict | None = None) -> dict:
    cmd = ["cf", "curl", path, "-X", method]
    if body is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(body)])
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    doc = json.loads(proc.stdout) if proc.stdout.strip() else {}
    if isinstance(doc, dict) and doc.get("errors"):
        raise SystemExit(f"cf curl {method} {path.split('?')[0]}: {doc['errors'][0].get('detail')}")
    return doc


def guid_of(kind: str, name: str, space: str | None = None) -> str | None:
    query = f"/v3/{kind}?names={name}&per_page=5"
    if space:
        query += f"&space_guids={space}"
    rows = cf_curl(query).get("resources") or []
    return rows[0]["guid"] if rows else None


def space_guid() -> str:
    org = guid_of("organizations", ORG)
    guid = cf_curl(f"/v3/spaces?names={SPACE}&organization_guids={org}").get("resources") or []
    if not guid:
        raise SystemExit(f"missing space {SPACE}")
    return guid[0]["guid"]


def app_env(guid: str) -> dict:
    return dict(cf_curl(f"/v3/apps/{guid}/environment_variables").get("var") or {})


def set_env(app: str, updates: dict) -> None:
    updates = {k: v for k, v in updates.items() if v}
    if not updates:
        return
    guid = guid_of("apps", app, space_guid())
    cf_curl(f"/v3/apps/{guid}/environment_variables", "PATCH", {"var": updates})
    print("env", app, "keys", ",".join(sorted(updates)), flush=True)


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


def ups(name: str, credentials: dict, tags: list[str] | None = None) -> None:
    """Create or update a user-provided service in this space."""
    space = space_guid()
    body: dict = {"credentials": credentials}
    if tags is not None:
        body["tags"] = tags
    guid = guid_of("service_instances", name, space)
    if guid:
        cf_curl(f"/v3/service_instances/{guid}", "PATCH", body)
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
        sys.stderr.write(proc.stdout[-800:] + proc.stderr[-800:])
        raise SystemExit(f"bind {service} to {app} failed")


def write_manifest(app: dict) -> Path:
    path = Path(tempfile.mkdtemp(prefix="metal-manifest-")) / "manifest.yml"
    path.write_text(json.dumps({"applications": [app]}, indent=2) + "\n", encoding="utf-8")
    return path


def push(app: dict, start: bool = True) -> None:
    args = ["push", "-f", str(write_manifest(app))]
    if not start:
        args.append("--no-start")
    proc = subprocess.run(["cf", *args], text=True)
    if proc.returncode != 0:
        raise SystemExit(f"cf push {app['name']} failed")


def health(url: str) -> int:
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(url, timeout=15, context=ctx) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return 0


def issuer_up(clients: dict) -> bool:
    """Sign in with a real agent client. An empty POST answers 500 on a healthy issuer."""
    ctx = ssl._create_unverified_context()
    code = 0
    for client in clients.values():
        client_id = client.get("client_id") or client.get("clientId") or ""
        client_secret = client.get("client_secret") or client.get("secret") or ""
        if not client_id or not client_secret:
            continue
        form = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
        ).encode()
        req = urllib.request.Request(TOKEN_URL, data=form, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                code = resp.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except OSError:
            code = 0
        break
    print("AgentMinder client sign-in HTTP", code, flush=True)
    return code == 200


def door_app(
    name: str,
    path: Path,
    memory: str,
    disk: str,
    command: str,
    env: dict,
    invocation_timeout: int = 10,
) -> dict:
    return {
        "name": name,
        "path": str(path),
        "memory": memory,
        "disk_quota": disk,
        "instances": 1,
        "timeout": 180,
        "health-check-type": "http",
        "health-check-http-endpoint": "/health",
        "health-check-invocation-timeout": invocation_timeout,
        "buildpacks": ["python_buildpack"],
        "command": command,
        "routes": [{"route": f"{name}.{DOMAIN}"}],
        "env": env,
    }


def stage_vcf() -> Path:
    dest = Path(tempfile.mkdtemp(prefix="metal-vcf-mcp-"))
    shutil.copytree(VCF_SRC / "src" / "vcf_mcp", dest / "vcf_mcp", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(VCF_SRC / "specs", dest / "specs")
    # Addresses only. The hosts file holds lab names, no credentials.
    shutil.copy(VCF_HOSTS, dest / "hosts.json")
    (dest / "requirements.txt").write_text(
        "mcp>=2.0.0\nhttpx>=0.27\nPyYAML>=6.0\nuvicorn>=0.30\nstarlette>=0.37\nPyJWT[crypto]>=2.8\n",
        encoding="utf-8",
    )
    (dest / "runtime.txt").write_text("python-3.12.x\n", encoding="utf-8")
    return dest


def stage_avi() -> Path:
    dest = Path(tempfile.mkdtemp(prefix="metal-avi-mcp-"))
    for name in ("server.py", "client.py", "mcp_http.py"):
        shutil.copy(AVI_SRC / name, dest / name)
    # The same AgentMinder token check the Kubernetes door uses.
    shutil.copy(K8S_SRC / "idsp_bearer.py", dest / "idsp_bearer.py")
    (dest / "requirements.txt").write_text("PyJWT[crypto]>=2.8\n", encoding="utf-8")
    (dest / "runtime.txt").write_text("python-3.12.x\n", encoding="utf-8")
    return dest


def _guest_token(account: str) -> str:
    """Mint a guest-cluster token. The value stays in the command output only."""
    kube = os.environ.get("KUBECONFIG") or str(Path.home() / ".kube" / "agentminder")
    proc = subprocess.run(
        ["kubectl", "--kubeconfig", kube, "-n", "k8s-mcp", "create", "token", account, "--duration=8760h"],
        check=True,
        text=True,
        capture_output=True,
    )
    token = proc.stdout.strip()
    if token.count(".") != 2:
        raise SystemExit(f"no token for {account}")
    return token


def diag_credentials(copied: dict) -> dict:
    """Read token for the diagnostic account, fault token for scale and delete.

    The diagnostic agent uses the diagnostic account, not an account that
    can patch and create outside this space.
    """
    server = str(copied.get("server") or "").strip()
    if not server.startswith("https://"):
        raise SystemExit("k8s-mcp-cluster copy has no server")
    return {
        "server": server,
        "namespace": "k8s-mcp",
        "token": _guest_token("k8s-diag"),
        "fault_token": _guest_token("k8s-mcp-fault"),
    }


def push_k8s() -> None:
    # Kubernetes. Same tree and size as the earlier k8s-mcp app.
    cluster = guid_of("service_instances", "k8s-mcp-cluster", space_guid())
    if not cluster:
        raise SystemExit(
            "k8s-mcp-cluster is missing in the Goad space. Create it from the approved PLAN.md. Do not copy it from another org."
        )
    # Put the diagnostic and fault accounts on this space's own service.
    copied = cf_curl(f"/v3/service_instances/{cluster}/credentials")
    ups("k8s-mcp-cluster", diag_credentials(copied))
    k8s = DOORS["k8s"]
    push(
        door_app(
            k8s,
            K8S_SRC,
            # 128M was enough for the process (about 25M resident). The cell
            # killed it because the 10s health check timed out during a stall,
            # exit 143, not an out-of-memory kill. 256M is headroom. 60s gives
            # the probe time to return when the cell is slow.
            "256M",
            "512M",
            "python k8s_mcp.py",
            {
                "MCP_RESOURCE_URL": f"https://{k8s}.{DOMAIN}/mcp",
                "IDSP_ISSUER": ISSUER,
                # Guest API calls outlast the 8 second default. INS-283.
                "K8S_API_TIMEOUT": "40",
            },
            invocation_timeout=60,
        ),
        start=False,
    )
    # A binding keeps the credentials it had when it was created.
    cf("unbind-service", k8s, "k8s-mcp-cluster", check=False)
    bind(k8s, "k8s-mcp-cluster")
    tokens = load_env(SECRETS / "k8s-mcp.env")
    set_env(k8s, {key: tokens.get(key, "") for key in ("MCP_READ_TOKEN", "MCP_WRITE_TOKEN")})
    cf("restart", k8s)


def push_vcf() -> None:
    # VCF. Canonical vcf-mcp repo, lab names in hosts.json.
    vcf = DOORS["vcf"]
    push(
        door_app(
            vcf,
            stage_vcf(),
            "1G",
            "2G",
            "python -m vcf_mcp serve-http",
            {
                "PYTHONUNBUFFERED": "1",
                "VCF_MCP_HOSTS_FILE": "/home/vcap/app/hosts.json",
                "VCF_MCP_SPEC_DIR": "/home/vcap/app/specs",
                "VCF_ALLOWED_HOSTS": f"{vcf}.{DOMAIN}",
                "VCF_MCP_RESOURCE_URL": f"https://{vcf}.{DOMAIN}/mcp",
                "VCF_MCP_AUDIT_LOG": "/dev/stdout",
                "VCF_MCP_VERIFY_TLS": "0",
                "VCF_MCP_OAUTH_TLS_VERIFY": "0",
                # Demo only. Replays the recorded 21:06 UTC disk sample.
                # Unset it, or set it to off, to read VCF Operations again.
                "VCF_DISK_LATENCY_REPLAY": "on",
                # One appliance read, and one inventory, must finish inside
                # this. The sidecar otherwise waits 300s and the chat dies.
                "VCF_HTTP_TIMEOUT": "8",
            },
            # The same slow-cell headroom as the Kubernetes door. A push
            # without it reset the live 60s to 10s.
            invocation_timeout=60,
        ),
        start=False,
    )
    mcp_space = guid_of("spaces", "mcp")
    old_vcf = guid_of("apps", "vcf-mcp", mcp_space)
    copied = app_env(old_vcf) if old_vcf else {}
    set_env(
        vcf,
        {
            **{k: copied.get(k, "") for k in ("NESTED_VCSA_PASSWORD", "NSX_ADMIN_PASSWORD", "SDDC_MANAGER_PASSWORD")},
            "VCF_READ_TOKEN": load_env(SECRETS / "vcf-mcp-http.env").get("VCF_READ_TOKEN", ""),
            "VCF_ADMIN_TOKEN": load_env(SECRETS / "vcf-mcp.env").get("VCF_ADMIN_TOKEN", ""),
            "VCF_DISK_LATENCY_REPLAY": "on",
            "VCF_HTTP_TIMEOUT": "8",
        },
    )
    cf("restart", vcf)


def push_avi() -> None:
    # Avi. Standalone controller door from this repo.
    avi = DOORS["avi"]
    avi_file = load_env(SECRETS / "avi-mcp.env")
    push(
        door_app(
            avi,
            stage_avi(),
            "128M",
            "512M",
            "python server.py",
            {
                "AVI_CONTROLLER": avi_file.get("AVI_CONTROLLER") or "${AVI_CONTROLLER_HOST}",
                "AVI_USERNAME": avi_file.get("AVI_USERNAME") or "admin",
                "MCP_RESOURCE_URL": f"https://{avi}.{DOMAIN}/mcp",
                "IDSP_ISSUER": ISSUER,
                "IDSP_GATEWAY_RESOURCE": AVI_GATEWAY,
            },
        ),
        start=False,
    )
    sddc = load_env(Path(avi_file["SDDC_ENV_FILE"])) if avi_file.get("SDDC_ENV_FILE") else {}
    set_env(
        avi,
        {
            "MCP_READ_TOKEN": avi_file.get("MCP_READ_TOKEN", ""),
            "MCP_WRITE_TOKEN": avi_file.get("MCP_WRITE_TOKEN", ""),
            "AVI_PASSWORD": sddc.get(avi_file.get("SDDC_PASSWORD_KEY") or "NSX_ADMIN_PASSWORD", ""),
        },
    )
    cf("restart", avi)


def live_token() -> str:
    """Bearer the incident agent and the company watch share. Never printed."""
    current = load_env(LIVE_SECRETS)
    token = current.get("MCP_TOKEN") or ""
    if token:
        return token
    token = os.urandom(32).hex()
    LIVE_SECRETS.parent.mkdir(parents=True, exist_ok=True)
    LIVE_SECRETS.write_text(f"MCP_TOKEN={token}\n", encoding="utf-8")
    LIVE_SECRETS.chmod(0o600)
    return token


def stage_live() -> Path:
    dest = Path(tempfile.mkdtemp(prefix="metal-incident-live-"))
    orch = dest / "orchestrator"
    orch.mkdir()
    names = (
        "__init__.py", "envfile.py", "findings.py", "jev.py", "qwen.py", "reasoning.py",
        "tanzu_agents.py", "topology.py", "enrich.py", "orchestrator.py", "skill_loader.py",
        "specialists.py", "k8s.py", "incident_title.py", "incident_live.py",
    )
    for name in names:
        shutil.copy(ROOT / "orchestrator" / name, orch / name)
    shutil.copytree(ROOT / "topology", dest / "topology")
    shutil.copytree(ROOT / "skills", dest / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (dest / "requirements.txt").write_text("pydantic>=2\n", encoding="utf-8")
    (dest / "runtime.txt").write_text("python-3.12.x\n", encoding="utf-8")
    return dest


def push_live() -> None:
    """The incident agent's enrichment tools. No Kubernetes or VCF grant."""
    cf("target", "-o", ORG, "-s", SPACE)
    demo_env = load_env(ROOT / ".env")
    push(
        door_app(
            LIVE_APP,
            stage_live(),
            "512M",
            "1G",
            "python3 orchestrator/incident_live.py",
            {},
            invocation_timeout=60,
        ),
        start=False,
    )
    set_env(
        LIVE_APP,
        {
            "MCP_TOKEN": live_token(),
            "JEV_BASE_URL": demo_env.get("JEV_BASE_URL", ""),
            "JEV_API_KEY": demo_env.get("JEV_API_KEY", ""),
            "JEV_MODEL": demo_env.get("JEV_MODEL", ""),
            "DGX_BASE_URL": demo_env.get("DGX_BASE_URL", ""),
            "DGX_MODEL": demo_env.get("DGX_MODEL", ""),
            "DGX_API_KEY": demo_env.get("DGX_API_KEY", ""),
        },
    )
    cf("start", LIVE_APP)
    print(LIVE_APP, "health HTTP", health(f"https://{LIVE_APP}.{DOMAIN}/health"), flush=True)


def bind_incident_tools(app: str) -> None:
    """User-provided MCP for enrichment. Not an AgentMinder Kubernetes or VCF grant."""
    if app != "incident-response-agent":
        return
    ups(
        ORCH_SERVICE,
        {
            "url": f"https://{LIVE_APP}.{DOMAIN}/mcp",
            "api_key": live_token(),
            "auth_type": "bearer",
        },
        ["mcp-server"],
    )
    bind(app, ORCH_SERVICE)


def push_doors(which: list[str]) -> None:
    cf("target", "-o", ORG, "-s", SPACE)
    steps = {"k8s": push_k8s, "vcf": push_vcf, "avi": push_avi}
    for door in which or list(steps):
        steps[door]()
    for name in DOORS.values():
        print(name, "health HTTP", health(f"https://{name}.{DOMAIN}/health"), flush=True)


def ensure_llm() -> None:
    if guid_of("service_instances", LLM_SERVICE, space_guid()):
        return
    # ai-models plans are not shareable, so this space gets its own instance.
    cf("create-service", LLM_OFFERING, LLM_PLAN, LLM_SERVICE, "--wait")


def stage_agent(app: str) -> Path:
    dest = Path(tempfile.mkdtemp(prefix=f"{app}-")) / "app"
    shutil.copytree(
        AGENTS,
        dest,
        ignore=shutil.ignore_patterns("app.py", "roles", "__pycache__", "*.pyc"),
    )
    shutil.copy(AGENTS / "roles" / f"{app}.md", dest / "AGENTS.md")
    # Agent Builder loads skills from .agents/skills/<name>/SKILL.md.
    skill = app.replace("-", "_")
    target = dest / ".agents" / "skills" / skill
    target.mkdir(parents=True)
    shutil.copy(SKILLS / skill / "SKILL.md", target / "SKILL.md")
    shutil.copy(SCHEMA, target / "findings.schema.json")
    return dest


def agent_app(app: str, path: Path, *, sidecar: bool = True) -> dict:
    spec = {
        "name": app,
        "path": str(path),
        "memory": "384M",
        "disk_quota": "1G",
        "instances": 1,
        "timeout": 180,
        "health-check-type": "http",
        "health-check-http-endpoint": "/health",
        # The cell stalls. A 10s probe kills a healthy process the way it
        # killed metal-k8s-mcp. 60s is the same timeout the doors use.
        "health-check-invocation-timeout": 60,
        "buildpacks": ["python_buildpack", "agent_buildpack"],
        "env": {
            "TANZU_AGENT_ENABLE_DEBUG_UI": "true",
            "AGENTMINDER_CA_BUNDLE": "/home/vcap/app/sidecar/lab-ca.pem",
        },
        "routes": [{"route": f"{app}.{DOMAIN}"}],
    }
    # The official sidecar refuses to start with zero resources. An agent
    # with no door does not run it.
    if sidecar:
        spec["sidecars"] = [
            {
                "name": "agentminder-sdk",
                "process_types": ["web"],
                "command": "bash sidecar/run-sidecar.sh",
                "memory": "128M",
            }
        ]
    return spec


def gateway_routes() -> dict[str, str]:
    """AI Gateway route per door, read from each door app's env once registered."""
    space = space_guid()
    out = {}
    for door, name in DOORS.items():
        guid = guid_of("apps", name, space)
        url = app_env(guid).get("IDSP_GATEWAY_RESOURCE", "") if guid else ""
        if url:
            out[door] = url
    return out


def push_agents(which: list[str]) -> None:
    cf("target", "-o", ORG, "-s", SPACE)
    ensure_llm()
    clients = json.loads(AGENT_CLIENTS.read_text(encoding="utf-8")) if AGENT_CLIENTS.is_file() else {}
    up = issuer_up(clients)
    # Orchestrator client id and secret stay in a mode-600 file outside git.
    orch = load_env(SECRETS / "agentminder-orchestrator.env")
    gateway = gateway_routes()
    saved = json.loads(SIDECARS.read_text(encoding="utf-8")) if SIDECARS.is_file() else {}

    for app, doors in ROLES.items():
        if which and app not in which:
            continue
        push(agent_app(app, stage_agent(app), sidecar=bool(doors)), start=False)
        token = (saved.get(app) or {}).get("token") or os.urandom(32).hex()
        saved[app] = {"token": token}
        current = json.loads(SIDECARS.read_text(encoding="utf-8")) if SIDECARS.is_file() else {}
        current[app] = saved[app]
        SIDECARS.write_text(json.dumps(current, indent=1) + "\n", encoding="utf-8")
        SIDECARS.chmod(0o600)
        client = clients.get(app.replace("-", "_")) or {}
        # metal_music_grants.py writes clientId and secret. Older files
        # used client_id and client_secret. Accept both.
        client_id = client.get("client_id") or client.get("clientId") or ""
        client_secret = client.get("client_secret") or client.get("secret") or ""
        updates = {
            "AGENTMINDER_IDSP_URL": orch.get("AGENTMINDER_IDSP_URL") or ISSUER,
            "AGENTMINDER_ORCHESTRATOR_CLIENT_ID": orch.get("AGENTMINDER_ORCHESTRATOR_CLIENT_ID", ""),
            "AGENTMINDER_ORCHESTRATOR_CLIENT_SECRET": orch.get("AGENTMINDER_ORCHESTRATOR_CLIENT_SECRET", ""),
            "AGENTMINDER_ORCHESTRATOR_SCOPES": orch.get("AGENTMINDER_ORCHESTRATOR_SCOPES") or "urn:iam:myscopes",
            "AGENTMINDER_SIDECAR_AGENT_CLIENT_ID": client_id,
            "AGENTMINDER_SIDECAR_AGENT_CLIENT_SECRET": client_secret,
            "AGENTMINDER_SIDECAR_TOKEN": token,
        }
        # Tools are listed and called only through the gateway, so an agent
        # holds no direct VCF door token.
        for key in ("VCF_MCP_URL", "VCF_READ_TOKEN"):
            cf("unset-env", app, key, check=False)
        used = [d for d in doors if d in gateway]
        for index, door in enumerate(used):
            updates[f"AGENTMINDER_SIDECAR_RESOURCE_{index}_NAME"] = door
            updates[f"AGENTMINDER_SIDECAR_RESOURCE_{index}_URL"] = gateway[door]
            updates[f"AGENTMINDER_SIDECAR_RESOURCE_{index}_AUDIENCE"] = gateway[door]
        set_env(app, updates)
        for index in range(len(used), len(DOORS)):
            for suffix in ("NAME", "URL", "AUDIENCE"):
                cf("unset-env", app, f"AGENTMINDER_SIDECAR_RESOURCE_{index}_{suffix}", check=False)
        for door in doors:
            service = f"sc-{app}-{door}"
            ups(
                service,
                {
                    "url": f"http://127.0.0.1:8181/mcp?resource={door}",
                    "api_key": token,
                    "auth_type": "bearer",
                },
                ["mcp-server"],
            )
            bind(app, service)
        for door in DOORS:
            if door not in doors:
                cf("unbind-service", app, f"sc-{app}-{door}", check=False)
        bind(app, LLM_SERVICE)

        missing = [d for d in doors if d not in gateway]
        bind_incident_tools(app)
        if up and client_id and client_secret and not missing:
            cf("restart", app)
            continue
        # Stage only. Starting now would crash on the sidecar.
        out = cf("stage-package", app).stdout
        droplet = next((line.split()[-1] for line in out.splitlines() if "droplet guid" in line.lower()), "")
        if droplet:
            cf("set-droplet", app, droplet)
        why = []
        if not up:
            why.append("issuer down")
        if not client_id or not client_secret:
            why.append("no AgentMinder client")
        if missing:
            why.append("no gateway route for " + ",".join(missing))
        print(app, "staged and stopped:", "; ".join(why), flush=True)


def main() -> None:
    if not SPACE:
        raise SystemExit(
            "GOAD_VCFA_SPACE is blank. Inventory org Goad, write PLAN.md, and wait for the Captain. See ASSEMBLE.md Step 0."
        )
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    rest = sys.argv[2:]
    if what in ("live", "all"):
        push_live()
    if what in ("mcp", "all"):
        push_doors(rest if what == "mcp" else [])
    if what in ("agents", "all"):
        push_agents(rest if what == "agents" else [])


if __name__ == "__main__":
    main()
