#!/usr/bin/env python3
"""Kubernetes MCP — list and manage workloads on the bound cluster.

Uses CUPS `brain-vks` (or K8S_API_SERVER + K8S_TOKEN). Never prints tokens.
Read tools are default. Write tools are limited (scale, create Job from CronJob).
No cluster-admin, no delete-namespace, no secrets dump.
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from mcp_http import McpServer, Tool, serve  # noqa: E402

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


# Prefer the live guest cluster CUPS. brain-vks may still hold a
# supervisor kubeconfig; that API times out and hangs Agent Builder.
_CUPS_NAMES = ("k8s-mcp-cluster", "k8s-mcp", "vks", "brain-vks")
API_TIMEOUT = 8
LOG_TIMEOUT = 20
_CERT_MODE = False
_SSL = CTX
_NAME = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
_REFUSED_NS = {"kube-system", "kube-public", "kube-node-lease"}
TOOL_LOG = Path(__file__).resolve().parent.parent / "tool-calls.jsonl"


def _vcap_vks() -> dict:
    raw = os.environ.get("VCAP_SERVICES") or ""
    if not raw:
        return {}
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    found: dict[str, dict] = {}
    for svc in doc.get("user-provided") or []:
        name = svc.get("name")
        if name in _CUPS_NAMES:
            found[str(name)] = dict(svc.get("credentials") or {})
    for name in _CUPS_NAMES:
        if name in found:
            return found[name]
    return {}


def _from_kubeconfig(raw: str) -> tuple[str, str, str]:
    """Read server / token / namespace from a kubeconfig string.

    Live CUPS ``brain-vks`` stores ``kubeconfig``, not loose server/token
    keys. Do not log the document.
    """
    import re

    def first(key: str) -> str:
        m = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(\S+)", raw)
        return (m.group(1) if m else "").strip().strip("'\"")

    server = first("server")
    token = first("token")
    ns = first("namespace") or "default"
    return server.rstrip("/"), token, ns


def _kubeconfig_text() -> str:
    raw_path = (os.environ.get("KUBECONFIG") or "").split(":")[0].strip()
    candidate = Path(raw_path) if raw_path else Path.home() / ".kube" / "agentminder"
    if not candidate.is_file():
        return ""
    return candidate.read_text(encoding="utf-8")


def _client_cert_material(raw: str) -> tuple[str, str] | None:
    """Return (cert_b64, key_b64) for the current context, or None.

    Does not write files and does not log the material.
    """
    try:
        import yaml
    except ImportError:
        return None
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        return None
    users = {
        item.get("name"): (item.get("user") or {})
        for item in (doc.get("users") or [])
        if isinstance(item, dict)
    }
    chosen: dict = {}
    current = doc.get("current-context")
    for item in doc.get("contexts") or []:
        if isinstance(item, dict) and item.get("name") == current:
            chosen = item.get("context") or {}
            break
    user = users.get(chosen.get("user")) or {}
    cert = user.get("client-certificate-data")
    key = user.get("client-key-data")
    if not isinstance(cert, str) or not isinstance(key, str) or not cert or not key:
        return None
    return cert, key


def _ssl_from_kubeconfig(raw: str) -> ssl.SSLContext | None:
    material = _client_cert_material(raw)
    if not material:
        return None
    dest = Path.home() / "secrets" / "k8s-mcp-client"
    dest.mkdir(parents=True, exist_ok=True)
    dest.chmod(0o700)
    cert_path = dest / "client.crt"
    key_path = dest / "client.key"
    cert_path.write_bytes(base64.b64decode(material[0]))
    key_path.write_bytes(base64.b64decode(material[1]))
    cert_path.chmod(0o600)
    key_path.chmod(0o600)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return ctx


def _endpoint() -> tuple[str, str, str]:
    global _CERT_MODE, _SSL
    creds = _vcap_vks()
    server = (
        (creds.get("server") or "").strip()
        or (os.environ.get("K8S_API_SERVER") or "").strip()
    )
    token = (
        (creds.get("token") or "").strip()
        or (os.environ.get("K8S_TOKEN") or "").strip()
    )
    ns = (
        (creds.get("namespace") or "").strip()
        or (os.environ.get("K8S_NAMESPACE") or "default").strip()
    )
    if (not server or not token) and creds.get("kubeconfig"):
        kc = creds.get("kubeconfig")
        if isinstance(kc, str):
            server, token, kns = _from_kubeconfig(kc)
            ns = kns or ns or "default"
            if server and not token:
                ctx = _ssl_from_kubeconfig(kc)
                if ctx is not None:
                    _SSL = ctx
                    _CERT_MODE = True
    if not server or (not token and not _CERT_MODE):
        text = _kubeconfig_text()
        if text:
            kserver, ktoken, kns = _from_kubeconfig(text)
            server = server or kserver
            token = token or ktoken
            ns = kns or ns or "default"
            if server and not token:
                ctx = _ssl_from_kubeconfig(text)
                if ctx is not None:
                    _SSL = ctx
                    _CERT_MODE = True
    if not server or (not token and not _CERT_MODE):
        raise ValueError("Kubernetes API not configured — bind CUPS k8s-mcp-cluster to k8s-mcp")
    return server.rstrip("/"), token, ns


def _fault_token() -> str:
    """Kube token for the fault account. Never the diagnostic account."""
    creds = _vcap_vks()
    token = (creds.get("fault_token") or os.environ.get("K8S_FAULT_TOKEN") or "").strip()
    if not token:
        raise ValueError("fault identity is not configured")
    return token


def _api(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: float | None = None,
    *,
    fault: bool = False,
) -> dict:
    status, raw = _request(method, path, body, timeout, fault=fault)
    if not raw:
        return {"ok": True, "status": status}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "status": status, "text": raw[:4000]}
    return parsed if isinstance(parsed, dict) else {"ok": True, "items": parsed}


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: float | None = None,
    *,
    fault: bool = False,
) -> tuple[int, str]:
    server, token, _ = _endpoint()
    if fault:
        token = _fault_token()
    # The guest API sometimes answers slowly. The default stays short.
    # A local door may set K8S_API_TIMEOUT when that default is too tight.
    if timeout is None and os.environ.get("K8S_API_TIMEOUT"):
        limit = float(os.environ["K8S_API_TIMEOUT"])
    else:
        limit = API_TIMEOUT if timeout is None else timeout
    url = server + path
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=limit, context=_SSL) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"message": raw[:300]}
        message = detail.get("message") if isinstance(detail, dict) else detail
        raise ValueError(f"Kubernetes HTTP {e.code}: {message}") from e
    except URLError as e:
        raise ValueError(f"Kubernetes unreachable: {e.reason}") from e
    except TimeoutError as e:
        raise ValueError(f"Kubernetes unreachable: timed out after {limit}s") from e


def _pod_names(ns: str) -> list[str]:
    doc = _api("GET", f"/api/v1/namespaces/{ns}/pods")
    names = []
    for item in doc.get("items") or []:
        name = str((item.get("metadata") or {}).get("name") or "")
        if name:
            names.append(name)
    return names


def _resolve_pod_name(ns: str, requested: str) -> str:
    """Map a PII-rewritten pod name back to the one live pod it still identifies.

    The model path rewrites a suffix into a phrase, or into a placeholder
    such as <US_DRIVER_LICENSE>. The part before that rewrite still names
    one pod. A name that is already live is returned unchanged.
    """
    names = _pod_names(ns)
    if requested in names:
        return requested
    probe = requested.split("<", 1)[0].rstrip("-")
    if probe and probe != requested:
        hits = [name for name in names if name == probe or name.startswith(probe + "-")]
        if len(hits) == 1:
            return hits[0]
    for index in range(len(requested), 9, -1):
        if index != len(requested) and requested[index - 1] != "-":
            continue
        prefix = requested[:index]
        hits = [name for name in names if name.startswith(prefix)]
        if len(hits) == 1:
            return hits[0]
    return requested


def _ns_name(args: dict) -> tuple[str, str]:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    name = str(args.get("name") or "").strip()
    if ns in _REFUSED_NS:
        raise ValueError("refusing kube-system, kube-public, and kube-node-lease")
    if not _NAME.match(ns):
        raise ValueError("namespace is not a DNS name")
    if not name or not _NAME.match(name):
        raise ValueError("name is required and must be a DNS name")
    return ns, name


def log_tool_call(server: str, tool: str, ok: bool, door: str = "mcp") -> None:
    """Append one tool call. No arguments, no tokens."""
    row = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "door": door,
        "server": server,
        "tool": tool,
        "ok": bool(ok),
    }
    TOOL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TOOL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _on_call(name: str, _role: str, ok: bool) -> None:
    log_tool_call("k8s-mcp", name, ok, door="mcp")


def k8s_cluster_info(_args: dict) -> dict:
    server, _, default_ns = _endpoint()
    ver = _api("GET", "/version")
    return {
        "api_server": server.split("//")[-1][:80],
        "default_namespace": default_ns,
        "version": {
            "major": ver.get("major"),
            "minor": ver.get("minor"),
            "gitVersion": ver.get("gitVersion"),
            "platform": ver.get("platform"),
        },
        "note": "Bound guest / workload cluster. Supervisor admin is a separate kubeconfig.",
    }


def k8s_list_nodes(_args: dict) -> dict:
    doc = _api("GET", "/api/v1/nodes")
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        status = item.get("status") or {}
        conditions = status.get("conditions") or []
        ready = next(
            (c.get("status") for c in conditions if c.get("type") == "Ready"),
            "Unknown",
        )
        pressure = next(
            (c.get("status") for c in conditions if c.get("type") == "DiskPressure"),
            "Unknown",
        )
        alloc = status.get("allocatable") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "ready": ready == "True",
                "disk_pressure": pressure == "True",
                "ephemeral_storage": alloc.get("ephemeral-storage"),
                "roles": [
                    k.replace("node-role.kubernetes.io/", "")
                    for k in (meta.get("labels") or {})
                    if k.startswith("node-role.kubernetes.io/")
                ],
            }
        )
    return {"count": len(rows), "nodes": rows}


def k8s_list_namespaces(_args: dict) -> dict:
    try:
        doc = _api("GET", "/api/v1/namespaces")
        names = [i["metadata"]["name"] for i in doc.get("items") or []]
        return {"count": len(names), "namespaces": names, "scope": "cluster"}
    except ValueError as e:
        # Namespaced SA often cannot list all namespaces — report home ns
        _, _, ns = _endpoint()
        return {
            "count": 1,
            "namespaces": [ns],
            "scope": "bound-namespace-only",
            "note": str(e)[:160],
        }


def k8s_list_pods(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    doc = _api("GET", f"/api/v1/namespaces/{ns}/pods")
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        status = item.get("status") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "phase": status.get("phase"),
                "node": status.get("hostIP") or (status.get("nominatedNodeName")),
                "restarts": sum(
                    (c.get("restartCount") or 0)
                    for c in (status.get("containerStatuses") or [])
                ),
            }
        )
    return {"namespace": ns, "count": len(rows), "pods": rows[:80], "truncated": len(rows) > 80}


def k8s_list_deployments(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    doc = _api("GET", f"/apis/apps/v1/namespaces/{ns}/deployments")
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        status = item.get("status") or {}
        spec = item.get("spec") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "replicas": spec.get("replicas"),
                "ready": status.get("readyReplicas") or 0,
                "available": status.get("availableReplicas") or 0,
            }
        )
    return {"namespace": ns, "count": len(rows), "deployments": rows}


def k8s_list_cronjobs(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    doc = _api("GET", f"/apis/batch/v1/namespaces/{ns}/cronjobs")
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "schedule": spec.get("schedule"),
                "suspend": bool(spec.get("suspend")),
            }
        )
    return {"namespace": ns, "count": len(rows), "cronjobs": rows}


def k8s_list_jobs(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    doc = _api("GET", f"/apis/batch/v1/namespaces/{ns}/jobs")
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        status = item.get("status") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "succeeded": status.get("succeeded") or 0,
                "failed": status.get("failed") or 0,
                "active": status.get("active") or 0,
            }
        )
    return {"namespace": ns, "count": len(rows), "jobs": rows[:60], "truncated": len(rows) > 60}


def k8s_scale_deployment(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    name = str(args.get("name") or "").strip()
    replicas = int(args.get("replicas") if args.get("replicas") is not None else -1)
    if not name:
        raise ValueError("name required")
    if replicas < 0 or replicas > 20:
        raise ValueError("replicas must be 0..20 on this stage")
    path = f"/apis/apps/v1/namespaces/{ns}/deployments/{name}/scale"
    current = _api("GET", path, fault=True)
    body = {
        "apiVersion": "autoscaling/v1",
        "kind": "Scale",
        "metadata": {"name": name, "namespace": ns, "resourceVersion": (current.get("metadata") or {}).get("resourceVersion")},
        "spec": {"replicas": replicas},
    }
    out = _api("PUT", path, body, fault=True)
    return {
        "namespace": ns,
        "name": name,
        "replicas": ((out.get("spec") or {}).get("replicas")),
        "ok": True,
    }


def k8s_create_job_from_cronjob(args: dict) -> dict:
    """Create a one-shot Job from an existing CronJob (manual trigger)."""
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    name = str(args.get("name") or "").strip()
    if not name:
        raise ValueError("CronJob name required")
    cj = _api("GET", f"/apis/batch/v1/namespaces/{ns}/cronjobs/{name}")
    job_template = ((cj.get("spec") or {}).get("jobTemplate") or {})
    job_spec = job_template.get("spec") or {}
    suffix = os.urandom(3).hex()
    job_name = f"{name}-manual-{suffix}"[:63]
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": ns,
            "labels": {"stage-chat": "true", "cronjob": name},
        },
        "spec": job_spec,
    }
    created = _api("POST", f"/apis/batch/v1/namespaces/{ns}/jobs", job)
    return {
        "ok": True,
        "namespace": ns,
        "cronjob": name,
        "job": (created.get("metadata") or {}).get("name"),
    }


def k8s_get(args: dict) -> dict:
    ns, name = _ns_name(args)
    kind = str(args.get("kind") or "pod").strip().lower()
    paths = {
        "pod": f"/api/v1/namespaces/{ns}/pods/{name}",
        "deployment": f"/apis/apps/v1/namespaces/{ns}/deployments/{name}",
        "service": f"/api/v1/namespaces/{ns}/services/{name}",
    }
    if kind not in paths:
        raise ValueError("kind must be pod, deployment, or service")
    doc = _api("GET", paths[kind])
    if kind == "deployment":
        return {"namespace": ns, "name": name, "kind": kind, "object": doc}
    meta = doc.get("metadata") or {}
    status = doc.get("status") or {}
    return {
        "namespace": ns,
        "name": meta.get("name"),
        "kind": kind,
        "phase": status.get("phase"),
        "node": (doc.get("spec") or {}).get("nodeName"),
        "object": doc if kind == "pod" else None,
    }


def k8s_pod_logs(args: dict) -> dict:
    args = dict(args)
    raw = str(args.get("name") or "")
    if "<" in raw:
        _, _, default_ns = _endpoint()
        ns = str(args.get("namespace") or default_ns).strip() or default_ns
        args["name"] = _resolve_pod_name(ns, raw)
    ns, name = _ns_name(args)
    name = _resolve_pod_name(ns, name)
    tail = int(args.get("tail") if args.get("tail") is not None else 80)
    tail = max(1, min(tail, 200))
    container = str(args.get("container") or "").strip()
    query = f"?tailLines={tail}"
    if container:
        if not _NAME.match(container):
            raise ValueError("container is not a DNS name")
        query += f"&container={container}"
    _status, text = _request(
        "GET", f"/api/v1/namespaces/{ns}/pods/{name}/log{query}", timeout=LOG_TIMEOUT
    )
    return {"namespace": ns, "name": name, "tail": tail, "log": text[-4000:]}


def k8s_events(args: dict) -> dict:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    if ns in _REFUSED_NS or not _NAME.match(ns):
        raise ValueError("namespace refused")
    name = str(args.get("name") or "").strip()
    path = f"/api/v1/namespaces/{ns}/events"
    if name:
        if not _NAME.match(name):
            raise ValueError("name is not a DNS name")
        path += f"?fieldSelector=involvedObject.name={name}"
    doc = _api("GET", path)
    rows = []
    for item in doc.get("items") or []:
        rows.append(
            {
                "reason": item.get("reason"),
                "message": (item.get("message") or "")[:240],
                "type": item.get("type"),
                "object": ((item.get("involvedObject") or {}).get("name")),
                "count": item.get("count"),
            }
        )
    rows = rows[-40:]
    return {"namespace": ns, "count": len(rows), "events": rows}


def k8s_set_service_endpoints(args: dict) -> dict:
    """Point one Service at one ready address.

    The endpoints controller on this guest cluster stops updating while
    it is crash-looping. A ready pod then stays off the Service and the
    ingress answers 503. This writes that one address. It is a bypass
    for a dead controller, not the normal design.
    """
    ns, name = _ns_name(args)
    ip = str(args.get("ip") or "").strip()
    port = int(args.get("port") or 0)
    if not ip or port < 1 or port > 65535:
        raise ValueError("ip and port required")
    path = f"/api/v1/namespaces/{ns}/endpoints/{name}"
    current = _api("GET", path, timeout=25)
    port_name = str(args.get("port_name") or "").strip()
    if not port_name:
        subsets = current.get("subsets") or []
        ports = (subsets[0].get("ports") if subsets else None) or []
        port_name = str((ports[0] or {}).get("name") or "http") if ports else "http"
    body = {
        "apiVersion": "v1",
        "kind": "Endpoints",
        "metadata": {
            "name": name,
            "namespace": ns,
            "resourceVersion": (current.get("metadata") or {}).get("resourceVersion"),
        },
        "subsets": [
            {
                "addresses": [{"ip": ip}],
                "ports": [{"name": port_name, "port": port, "protocol": "TCP"}],
            }
        ],
    }
    out = _api("PUT", path, body, timeout=25)
    subsets = out.get("subsets") or []
    addresses = (subsets[0].get("addresses") if subsets else None) or []
    return {
        "ok": True,
        "namespace": ns,
        "name": name,
        "ip": (addresses[0] or {}).get("ip") if addresses else ip,
        "port": port,
    }


def k8s_delete_pod(args: dict) -> dict:
    ns, name = _ns_name(args)
    out = _api("DELETE", f"/api/v1/namespaces/{ns}/pods/{name}", fault=True)
    return {"ok": True, "namespace": ns, "name": name, "status": (out.get("status") or out.get("code") or "deleted")}


def _pod_guard(pod: dict) -> None:
    if pod.get("kind") != "Pod" or pod.get("apiVersion") != "v1":
        raise ValueError("only a v1 Pod is accepted")
    spec = pod.get("spec") or {}
    if spec.get("hostNetwork") or spec.get("hostPID") or spec.get("hostIPC"):
        raise ValueError("host namespaces are refused")
    for volume in spec.get("volumes") or []:
        if "hostPath" in volume:
            raise ValueError("hostPath is refused")
    containers = list(spec.get("containers") or []) + list(spec.get("initContainers") or [])
    for container in containers:
        security = container.get("securityContext") or {}
        if security.get("privileged"):
            raise ValueError("privileged is refused")


# Security INS-278 item 1. Create is namespace-wide in Kubernetes, so the
# door only accepts the one pod that review approved.
_LOAD_NS = "metal-music-store"
_LOAD_NAME = "storage-load"
_LOAD_NODE = "${K8S_NODE_B}"


def _storage_load_shape(pod: dict, ns: str, name: str) -> None:
    if ns != _LOAD_NS or name != _LOAD_NAME:
        raise ValueError("create is only the approved storage-load pod")
    spec = pod.get("spec") or {}
    if spec.get("restartPolicy") != "Never":
        raise ValueError("restartPolicy must be Never")
    if spec.get("activeDeadlineSeconds") != 900:
        raise ValueError("activeDeadlineSeconds must be 900")
    if spec.get("nodeName") != _LOAD_NODE:
        raise ValueError("pod must stay on the approved node")
    if spec.get("initContainers"):
        raise ValueError("init containers are refused")
    containers = spec.get("containers") or []
    if len(containers) != 1:
        raise ValueError("one container only")
    limits = (containers[0].get("resources") or {}).get("limits") or {}
    if limits.get("cpu") != "500m" or limits.get("memory") != "128Mi":
        raise ValueError("cpu limit 500m and memory limit 128Mi")
    volumes = spec.get("volumes") or []
    if len(volumes) != 1 or (volumes[0].get("emptyDir") or {}).get("sizeLimit") != "2Gi":
        raise ValueError("one emptyDir volume with sizeLimit 2Gi")


def k8s_create_pod(args: dict) -> dict:
    pod = args.get("pod")
    if not isinstance(pod, dict):
        raise ValueError("pod object required")
    _pod_guard(pod)
    meta = pod.get("metadata") or {}
    ns, name = _ns_name({"namespace": meta.get("namespace"), "name": meta.get("name")})
    _storage_load_shape(pod, ns, name)
    created = _api("POST", f"/api/v1/namespaces/{ns}/pods", pod, fault=True)
    return {"ok": True, "namespace": ns, "name": (created.get("metadata") or {}).get("name") or name}


def _diag_ns(args: dict) -> str:
    _, _, default_ns = _endpoint()
    ns = str(args.get("namespace") or default_ns).strip() or default_ns
    if ns in _REFUSED_NS or not _NAME.match(ns):
        raise ValueError("namespace refused")
    return ns


def _pod_rows(ns: str) -> list[dict]:
    doc = _api("GET", f"/api/v1/namespaces/{ns}/pods", timeout=25)
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        containers = status.get("containerStatuses") or []
        restarts = sum(int(c.get("restartCount") or 0) for c in containers)
        ready = sum(1 for c in containers if c.get("ready"))
        phase = status.get("phase")
        rows.append(
            {
                "name": meta.get("name"),
                "phase": phase,
                "ready": ready,
                "containers": len(containers),
                "restarts": restarts,
                "node": spec.get("nodeName"),
                "healthy": phase == "Running" and ready == len(containers) and len(containers) > 0,
            }
        )
    return rows


def k8s_pod_health(args: dict) -> dict:
    ns = _diag_ns(args)
    rows = _pod_rows(ns)
    return {
        "namespace": ns,
        "count": len(rows),
        "unhealthy": sum(1 for row in rows if not row["healthy"]),
        "pods": rows[:40],
    }


def k8s_deployment_health(args: dict) -> dict:
    ns = _diag_ns(args)
    doc = _api("GET", f"/apis/apps/v1/namespaces/{ns}/deployments", timeout=25)
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        desired = int(spec.get("replicas") or 0)
        ready = int(status.get("readyReplicas") or 0)
        rows.append(
            {
                "name": meta.get("name"),
                "desired": desired,
                "ready": ready,
                "available": int(status.get("availableReplicas") or 0),
                "healthy": ready >= desired and desired > 0,
            }
        )
    return {
        "namespace": ns,
        "count": len(rows),
        "unhealthy": sum(1 for row in rows if not row["healthy"]),
        "deployments": rows,
    }


def k8s_pod_restarts(args: dict) -> dict:
    ns = _diag_ns(args)
    rows = [row for row in _pod_rows(ns) if row["restarts"] > 0]
    rows.sort(key=lambda row: row["restarts"], reverse=True)
    return {"namespace": ns, "pods_with_restarts": len(rows), "pods": rows[:40]}


def k8s_logs_tail(args: dict) -> dict:
    return k8s_pod_logs(args)


def k8s_resource_usage(args: dict) -> dict:
    ns = _diag_ns(args)
    try:
        doc = _api("GET", f"/apis/metrics.k8s.io/v1beta1/namespaces/{ns}/pods", timeout=25)
    except ValueError as exc:
        text = str(exc)
        if "404" in text or "403" in text or "HTTP" in text:
            return {
                "namespace": ns,
                "usage": None,
                "error": text[:240],
                "note": "The metrics API did not return usage. No usage number was invented.",
            }
        raise
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        containers = []
        for container in item.get("containers") or []:
            containers.append(
                {
                    "name": container.get("name"),
                    "cpu": (container.get("usage") or {}).get("cpu"),
                    "memory": (container.get("usage") or {}).get("memory"),
                }
            )
        rows.append({"name": meta.get("name"), "containers": containers})
    return {"namespace": ns, "count": len(rows), "usage": rows[:40]}


def k8s_endpoint_readiness(args: dict) -> dict:
    ns = _diag_ns(args)
    name = str(args.get("name") or "").strip()
    if name:
        if not _NAME.match(name):
            raise ValueError("name is not a DNS name")
        docs = [_api("GET", f"/api/v1/namespaces/{ns}/endpoints/{name}", timeout=25)]
    else:
        listed = _api("GET", f"/api/v1/namespaces/{ns}/endpoints", timeout=25)
        docs = listed.get("items") or []
    rows = []
    for doc in docs:
        meta = doc.get("metadata") or {}
        ready_ips = []
        not_ready = []
        ports = []
        for subset in doc.get("subsets") or []:
            ports = [p.get("port") for p in subset.get("ports") or []]
            ready_ips.extend(addr.get("ip") for addr in subset.get("addresses") or [])
            not_ready.extend(addr.get("ip") for addr in subset.get("notReadyAddresses") or [])
        rows.append(
            {
                "name": meta.get("name"),
                "ready": [ip for ip in ready_ips if ip],
                "not_ready": [ip for ip in not_ready if ip],
                "ports": ports,
                "ready_count": len([ip for ip in ready_ips if ip]),
            }
        )
    return {"namespace": ns, "count": len(rows), "endpoints": rows[:40]}


def k8s_ingress_status(args: dict) -> dict:
    ns = _diag_ns(args)
    doc = _api("GET", f"/apis/networking.k8s.io/v1/namespaces/{ns}/ingresses", timeout=25)
    classes = _api("GET", "/apis/networking.k8s.io/v1/ingressclasses", timeout=25)
    class_rows = []
    for item in classes.get("items") or []:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        class_rows.append({"name": meta.get("name"), "controller": spec.get("controller")})
    rows = []
    for item in doc.get("items") or []:
        meta = item.get("metadata") or {}
        spec = item.get("spec") or {}
        status = item.get("status") or {}
        rows.append(
            {
                "name": meta.get("name"),
                "class": spec.get("ingressClassName"),
                "hosts": [rule.get("host") for rule in spec.get("rules") or []],
                "load_balancer": (status.get("loadBalancer") or {}).get("ingress"),
            }
        )
    return {"namespace": ns, "ingresses": rows, "ingress_classes": class_rows}


def build() -> McpServer:
    s = McpServer("k8s-mcp", version="0.1.0")
    s.on_call = _on_call
    try:
        server, _, ns = _endpoint()
        s.health_extra = {
            "api": server.split("//")[-1][:60],
            "namespace": ns,
            "configured": True,
            "auth": "client-cert" if _CERT_MODE else "bearer",
        }
    except ValueError as e:
        s.health_extra = {"configured": False, "error": str(e)[:120]}

    empty = {"type": "object", "properties": {}}
    ns_schema = {
        "type": "object",
        "properties": {"namespace": {"type": "string", "description": "Kubernetes namespace"}},
    }
    s.add(Tool("k8s_cluster_info", "Show which Kubernetes API this MCP is bound to (version + home namespace).", empty, k8s_cluster_info, read_only=True))
    s.add(Tool("k8s_list_nodes", "List cluster nodes and how many are Ready. Use this for a node count.", empty, k8s_list_nodes, read_only=True))
    s.add(Tool("k8s_list_namespaces", "List namespaces this identity can see (or the bound home namespace).", empty, k8s_list_namespaces, read_only=True))
    s.add(Tool("k8s_list_pods", "List pods in a namespace (default: bound home namespace).", ns_schema, k8s_list_pods, read_only=True))
    s.add(Tool("k8s_list_deployments", "List Deployments in a namespace.", ns_schema, k8s_list_deployments, read_only=True))
    s.add(Tool("k8s_list_cronjobs", "List CronJobs in a namespace.", ns_schema, k8s_list_cronjobs, read_only=True))
    s.add(Tool("k8s_list_jobs", "List Jobs in a namespace.", ns_schema, k8s_list_jobs, read_only=True))
    s.add(
        Tool(
            "k8s_scale_deployment",
            "Scale a Deployment to 0..20 replicas (write).",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "replicas": {"type": "integer"},
                    "namespace": {"type": "string"},
                },
                "required": ["name", "replicas"],
            },
            k8s_scale_deployment,
            read_only=False,
        )
    )
    s.add(
        Tool(
            "k8s_create_job_from_cronjob",
            "Manually trigger a CronJob by creating a one-shot Job (write).",
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "CronJob name"},
                    "namespace": {"type": "string"},
                },
                "required": ["name"],
            },
            k8s_create_job_from_cronjob,
            read_only=False,
        )
    )
    s.add(Tool("k8s_get", "Read one pod, deployment, or service.", {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "description": "pod, deployment, or service"},
            "name": {"type": "string"},
            "namespace": {"type": "string"},
        },
        "required": ["name"],
    }, k8s_get, read_only=True))
    s.add(Tool("k8s_pod_logs", "Last lines of one container log.", {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "container": {"type": "string"},
            "tail": {"type": "integer"},
        },
        "required": ["name"],
    }, k8s_pod_logs, read_only=True))
    s.add(Tool("k8s_events", "Recent events in a namespace, optionally for one object.", {
        "type": "object",
        "properties": {
            "namespace": {"type": "string"},
            "name": {"type": "string"},
        },
    }, k8s_events, read_only=True))
    diag = {
        "type": "object",
        "properties": {"namespace": {"type": "string"}, "name": {"type": "string"}},
    }
    s.add(Tool("k8s_pod_health", "Pod phase, readiness, and whether each pod is healthy.", diag, k8s_pod_health, read_only=True))
    s.add(Tool("k8s_deployment_health", "Desired replicas against ready replicas.", diag, k8s_deployment_health, read_only=True))
    s.add(Tool("k8s_pod_restarts", "Pods whose containers have restarted.", diag, k8s_pod_restarts, read_only=True))
    s.add(Tool("k8s_logs_tail", "Last lines of one container log.", {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
            "container": {"type": "string"},
            "tail": {"type": "integer"},
        },
        "required": ["name"],
    }, k8s_logs_tail, read_only=True))
    s.add(Tool("k8s_resource_usage", "CPU and memory usage from the metrics API.", diag, k8s_resource_usage, read_only=True))
    s.add(Tool("k8s_endpoint_readiness", "Ready and not-ready addresses for Services.", diag, k8s_endpoint_readiness, read_only=True))
    s.add(Tool("k8s_ingress_status", "Ingress hosts, class, and load balancer addresses.", diag, k8s_ingress_status, read_only=True))
    s.add(Tool(
        "k8s_set_service_endpoints",
        "Point one Service at one pod address when the endpoints controller is not updating.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "namespace": {"type": "string"},
                "ip": {"type": "string"},
                "port": {"type": "integer"},
                "port_name": {"type": "string"},
            },
            "required": ["name", "namespace", "ip", "port"],
        },
        k8s_set_service_endpoints,
        read_only=False,
    ))
    s.add(Tool("k8s_delete_pod", "Delete one pod by name. Refuses system namespaces.", {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "namespace": {"type": "string"},
        },
        "required": ["name", "namespace"],
    }, k8s_delete_pod, read_only=False))
    s.add(Tool("k8s_create_pod", "Create the approved storage-load pod on the fault account. Refuses any other pod.", {
        "type": "object",
        "properties": {
            "pod": {"type": "object"},
        },
        "required": ["pod"],
    }, k8s_create_pod, read_only=False))
    return s


def _load_local_tokens() -> None:
    """Read bearer tokens from the home secrets file. Never print them."""
    path = Path.home() / "secrets" / "k8s-mcp.env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in ("MCP_READ_TOKEN", "MCP_WRITE_TOKEN", "KUBECONFIG"):
            os.environ.setdefault(key, value.strip().strip("'").strip('"'))


if __name__ == "__main__":
    _load_local_tokens()
    # A platform sets PORT and wants every interface. On agents-machine
    # the door stays on localhost unless MCP_HOST says otherwise.
    if os.environ.get("PORT"):
        bind_host = os.environ.get("HOST", "0.0.0.0")
        bind_port = int(os.environ["PORT"])
    else:
        bind_host = os.environ.get("MCP_HOST", "127.0.0.1")
        bind_port = int(os.environ.get("MCP_PORT", "8088"))
    serve(build(), host=bind_host, port=bind_port)
