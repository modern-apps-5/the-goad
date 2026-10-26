#!/usr/bin/env python3
"""Readiness of the Goad demo and the architecture map.

Writes demo_up for the existing boards, plus arch_up / arch_latency_ms /
arch_edge for the architecture board. Checks are read-only HTTP GETs and
TCP connects. No credentials are written into metrics.
"""
import json
import os
import socket
import ssl
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

CHECKS = (
    ("store", os.environ.get("STORE_URL", "http://music-store-1-service.music-store.svc:5000/")),
    ("users", os.environ.get("USERS_URL", "http://users-service.music-store.svc:5003/health")),
    ("zammad", os.environ.get("ZAMMAD_URL", "http://zammad-nginx.incident-tools.svc:8080/")),
    ("qwen", os.environ.get("QWEN_MODELS_URL", "")),
    ("clm", os.environ.get("CLM_URL", "")),
)
CTX = ssl._create_unverified_context()
LOCK = threading.Lock()
STATE = {"demo": {}, "arch": {}, "edges": []}
NODE_8 = "music-store-workers-6xtl4-wnr4j-8n8n5"
NODE_G = "music-store-workers-6xtl4-wnr4j-gjwhn"
KUBELET = "v1.36.2+vmware.2"
SUBTITLE = {
    "cluster": "Cluster",
    "host": "Host",
    "vmsvc": "VM Service",
    "database": "Database",
    "app": "App",
    "agent": "Agent",
    "mcp": "MCP",
    "model": "Model",
    "console": "Console",
    "service": "Service",
}


def item(i, title, kind, cluster, namespace, node, endpoint, protocol, version, mode, **extra):
    row = {
        "id": i,
        "title": title,
        "kind": kind,
        "cluster": cluster,
        "namespace": namespace,
        "node": node,
        "endpoint": endpoint,
        "protocol": protocol,
        "version": version,
        "mode": mode,
    }
    row.update(extra)
    return row


ARCH = (
    item("vks-api", "VKS API", "cluster", "music-store", "music-store-8q8l6", "-", "10.47.7.81:6443", "TCP", KUBELET, "tcp", host="10.47.7.81", port=6443, ip="10.47.7.81"),
    item("cp-pwtc2", "Control plane", "host", "music-store", "music-store-8q8l6", "music-store-k4sgg-pwtc2", "172.30.0.66:10250", "kube Ready", KUBELET + " best-effort-medium", "node", prom_node="music-store-k4sgg-pwtc2", host="172.30.0.66", port=10250, ip="172.30.0.66"),
    item("worker-8n8n5", "Worker 8n8n5", "host", "music-store", "music-store-8q8l6", NODE_8, "172.30.0.70:10250", "kube Ready", KUBELET + " best-effort-large", "node", prom_node=NODE_8, host="172.30.0.70", port=10250, ip="172.30.0.70"),
    item("worker-gjwhn", "Worker gjwhn", "host", "music-store", "music-store-8q8l6", NODE_G, "172.30.0.69:10250", "kube Ready", KUBELET + " best-effort-large", "node", prom_node=NODE_G, host="172.30.0.69", port=10250, ip="172.30.0.69"),
    item("am-api", "AgentMinder API", "cluster", "agentminder", "agentminder-z7v8k", "-", "10.47.7.77:6443", "TCP", KUBELET, "tcp", host="10.47.7.77", port=6443, ip="10.47.7.77"),
    item("am-cp", "AM control plane", "host", "agentminder", "agentminder-z7v8k", "agentminder-5nprd-9btlg", "172.30.0.34:10250", "kubelet", KUBELET, "kubelet", host="172.30.0.34", port=10250, ip="172.30.0.34"),
    item("am-w-7dsds", "AM worker 7dsds", "host", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-7dsds", "172.30.0.36:10250", "kubelet", KUBELET, "kubelet", host="172.30.0.36", port=10250, ip="172.30.0.36"),
    item("am-w-gpn6h", "AM worker gpn6h", "host", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-gpn6h", "172.30.0.35:10250", "kubelet", KUBELET, "kubelet", host="172.30.0.35", port=10250, ip="172.30.0.35"),
    item("users-vm", "Users VM", "vmsvc", "music-store", "music-store-8q8l6", "music-users", "http://10.47.7.52:5003/health", "HTTP", "ubuntu-24.04-cloud best-effort-small", "http", url="http://10.47.7.52:5003/health", ip="10.47.7.52"),
    item("shop-users", "Shop users", "service", "music-store", "music-store", "-", "http://users-service.music-store.svc:5003/health", "HTTP", "-", "http", url="http://users-service.music-store.svc:5003/health", ip="10.47.7.52"),
    item("dsm", "DSM catalog", "database", "music-store", "music-store-8q8l6", "-", "10.47.7.78:5432", "TCP", "16.14+vmware.v9.1.1.0", "tcp", host="10.47.7.78", port=5432, ip="10.47.7.78"),
    item("vcf-ops", "VCF Ops", "console", "vcf", "ops01", "-", "10.47.0.221:443", "TCP", "ops01.gpu.set.lab", "tcp", host="10.47.0.221", port=443, ip="10.47.0.221"),
    item("vcfa", "VCFA", "console", "vcf", "auto", "-", "10.47.0.224:443", "TCP", "auto.gpu.set.lab", "tcp", host="10.47.0.224", port=443, ip="10.47.0.224"),
    item("vcenter", "vCenter", "console", "vcf", "vc01", "-", "10.47.0.200:443", "TCP", "vc01.gpu.set.lab", "tcp", host="10.47.0.200", port=443, ip="10.47.0.200"),
    item("nsx", "NSX", "console", "vcf", "nsx01", "-", "10.47.0.230:443", "TCP", "nsx01.gpu.set.lab", "tcp", host="10.47.0.230", port=443, ip="10.47.0.230"),
    item("music", "Music shop", "app", "music-store", "music-store", NODE_8, "http://music-store-1-service.music-store.svc:5000/", "HTTP", "python:3.12-slim", "http", url="http://music-store-1-service.music-store.svc:5000/", ip="10.101.76.254"),
    item("chat", "Chat", "app", "music-store", "music-store", NODE_8, "http://chat-service.music-store.svc:5005/health", "HTTP", "python:3.12-slim", "http", url="http://chat-service.music-store.svc:5005/health", ip="10.111.73.154"),
    item("cart", "Cart", "app", "music-store", "music-store", NODE_8, "http://cart-service.music-store.svc:5002/health", "HTTP", "python:3.12-slim", "http", url="http://cart-service.music-store.svc:5002/health", ip="10.97.251.112"),
    item("order", "Order", "app", "music-store", "music-store", NODE_8, "http://order-service.music-store.svc:5001/health", "HTTP", "python:3.12-slim", "http", url="http://order-service.music-store.svc:5001/health", ip="10.111.74.18"),
    item("zammad", "Zammad", "app", "music-store", "incident-tools", "-", "http://zammad-nginx.incident-tools.svc:8080/", "HTTP", "-", "http", url="http://zammad-nginx.incident-tools.svc:8080/", ip="10.47.7.83"),
    item("zammad-db", "Zammad DB", "database", "music-store", "incident-tools", "-", "zammad-postgresql.incident-tools.svc:5432", "TCP", "-", "tcp", host="zammad-postgresql.incident-tools.svc", port=5432, ip="10.106.205.2"),
    item("zammad-redis", "Zammad Redis", "service", "music-store", "incident-tools", "-", "zammad-redis.incident-tools.svc:6379", "TCP", "-", "tcp", host="zammad-redis.incident-tools.svc", port=6379, ip="10.97.122.51"),
    item("zammad-cache", "Zammad cache", "service", "music-store", "incident-tools", "-", "zammad-memcached.incident-tools.svc:11211", "TCP", "-", "tcp", host="zammad-memcached.incident-tools.svc", port=11211, ip="10.109.25.157"),
    item("pii", "PII scrub", "app", "music-store", "metal-music-app-agentic-system", NODE_G, "http://pii-scrub.metal-music-app-agentic-system.svc:8080/health", "HTTP", "python:3.12-slim", "http", url="http://pii-scrub.metal-music-app-agentic-system.svc:8080/health", ip="10.105.6.138"),
    item("qwen", "Qwen", "model", "private-ai", "private-ai-hphfz", "-", "https://10.47.7.73", "HTTPS", "qwen-14b-xlarge", "qwen", ip="10.47.7.73"),
    item("am-ui", "AgentMinder", "console", "agentminder", "ssp", "-", "https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/", "HTTPS", "console", "http", url="https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/", ip="10.47.7.82"),
    item("clm", "CLM", "model", "private-ai", "-", "-", "not-installed", "-", "not-installed", "clm", ip="-"),
    item("orch", "Orchestrator", "app", "music-store", "metal-music-app-agentic-system", NODE_G, "http://orchestrator.metal-music-app-agentic-system.svc:8080/health", "HTTP", "python:3.12-slim", "http", url="http://orchestrator.metal-music-app-agentic-system.svc:8080/health", ip="10.100.115.123"),
    item("incident", "Incident agent", "agent", "tanzu-cf", "metal-music-app-agentic-system", "-", "https://incident-response-agent.apps.tp.gpu.set.lab/health", "HTTPS", "tanzu-agent 0.6.0", "http", url="https://incident-response-agent.apps.tp.gpu.set.lab/health"),
    item("cf-orch", "CF orchestrator", "agent", "tanzu-cf", "metal-music-app-agentic-system", "-", "https://metal-incident-live.apps.tp.gpu.set.lab/health", "HTTPS", "harness.py", "http", url="https://metal-incident-live.apps.tp.gpu.set.lab/health"),
    item("lb-agent", "LB agent", "agent", "tanzu-cf", "metal-music-app-agentic-system", "-", "https://lb-diagnostic-agent.apps.tp.gpu.set.lab/health", "HTTPS", "tanzu-agent 0.6.0", "http", url="https://lb-diagnostic-agent.apps.tp.gpu.set.lab/health"),
    item("k8s-agent", "K8s agent", "agent", "tanzu-cf", "metal-music-app-agentic-system", "-", "https://k8s-diagnostic-agent.apps.tp.gpu.set.lab/health", "HTTPS", "tanzu-agent 0.6.0", "http", url="https://k8s-diagnostic-agent.apps.tp.gpu.set.lab/health"),
    item("vcf-agent", "VCF agent", "agent", "tanzu-cf", "metal-music-app-agentic-system", "-", "https://vcf-diagnostic-agent.apps.tp.gpu.set.lab/health", "HTTPS", "tanzu-agent 0.6.0", "http", url="https://vcf-diagnostic-agent.apps.tp.gpu.set.lab/health"),
    item("avi-mcp", "Avi MCP", "mcp", "music-store", "metal-music-app-agentic-system", NODE_G, "http://avi-mcp.goad.gpu.set.lab/mcp", "MCP", "python:3.12-slim", "http", url="http://goad-avi-mcp.metal-music-app-agentic-system.svc:8080/health", ip="10.47.7.68"),
    item("k8s-mcp", "K8s MCP", "mcp", "music-store", "metal-music-app-agentic-system", NODE_8, "http://k8s-mcp.goad.gpu.set.lab/mcp", "MCP", "python:3.12-slim", "http", url="http://goad-k8s-mcp.metal-music-app-agentic-system.svc:8080/health", ip="10.47.7.85"),
    item("vcf-mcp", "VCF MCP", "mcp", "music-store", "metal-music-app-agentic-system", NODE_G, "http://vcf-mcp.goad.gpu.set.lab/mcp", "MCP", "python:3.12-slim", "http", url="http://goad-vcf-mcp.metal-music-app-agentic-system.svc:8080/health", ip="10.47.7.86"),
)

# Calls observed in this org. A path is up only when both ends are up.
EDGES = (
    ("e-music-chat", "music", "chat", "HTTP"),
    ("e-music-cart", "music", "cart", "HTTP"),
    ("e-music-order", "music", "order", "HTTP"),
    ("e-music-users", "music", "shop-users", "HTTP"),
    ("e-music-dsm", "music", "dsm", "TCP 5432"),
    ("e-chat-order", "chat", "order", "HTTP"),
    ("e-chat-dsm", "chat", "dsm", "TCP 5432"),
    ("e-chat-qwen", "chat", "qwen", "HTTPS"),
    ("e-incident-orch", "incident", "cf-orch", "HTTP"),
    ("e-incident-zammad", "incident", "zammad", "HTTPS"),
    ("e-cforch-lb", "cf-orch", "lb-agent", "HTTP"),
    ("e-cforch-k8s", "cf-orch", "k8s-agent", "HTTP"),
    ("e-cforch-vcf", "cf-orch", "vcf-agent", "HTTP"),
    ("e-cforch-zammad", "cf-orch", "zammad", "HTTPS"),
    ("e-cforch-qwen", "cf-orch", "qwen", "HTTPS"),
    ("e-lb-avi", "lb-agent", "avi-mcp", "MCP"),
    ("e-k8s-mcp", "k8s-agent", "k8s-mcp", "MCP"),
    ("e-vcf-mcp", "vcf-agent", "vcf-mcp", "MCP"),
    ("e-lb-am", "lb-agent", "am-ui", "OAuth"),
    ("e-k8s-am", "k8s-agent", "am-ui", "OAuth"),
    ("e-vcf-am", "vcf-agent", "am-ui", "OAuth"),
    ("e-lb-qwen", "lb-agent", "qwen", "HTTPS"),
    ("e-k8s-qwen", "k8s-agent", "qwen", "HTTPS"),
    ("e-vcf-qwen", "vcf-agent", "qwen", "HTTPS"),
    ("e-orch-qwen", "orch", "qwen", "HTTPS"),
    ("e-orch-music", "orch", "music", "HTTP"),
    ("e-zammad-db", "zammad", "zammad-db", "TCP 5432"),
    ("e-zammad-redis", "zammad", "zammad-redis", "TCP 6379"),
    ("e-zammad-cache", "zammad", "zammad-cache", "TCP 11211"),
)


def one(url: str, headers: dict | None = None) -> tuple[int, int]:
    if not url:
        return 0, 0
    start = time.monotonic()
    try:
        request = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(request, timeout=20, context=CTX) as response:
            body = response.read(4000)
            ok = 200 <= response.status < 400
            if "models" in url and b"qwen" not in body:
                ok = False
        return (1 if ok else 0), int((time.monotonic() - start) * 1000)
    except Exception:
        return 0, int((time.monotonic() - start) * 1000)


def catalog() -> int:
    host = os.environ.get("CATALOG_HOST", "postgres-service.music-store.svc")
    try:
        with socket.create_connection((host, 5432), 5):
            return 1
    except Exception:
        return 0


def check_http(url: str) -> tuple[int, int]:
    if not url:
        return 0, 0
    start = time.monotonic()
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=6, context=CTX) as response:
            response.read(200)
            ok = 200 <= response.status < 400
        return (1 if ok else 0), int((time.monotonic() - start) * 1000)
    except Exception:
        return 0, int((time.monotonic() - start) * 1000)


def check_tcp(host: str, port: int) -> tuple[int, int]:
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), 4):
            return 1, int((time.monotonic() - start) * 1000)
    except Exception:
        return 0, int((time.monotonic() - start) * 1000)


def music_node_ready() -> dict | None:
    query = 'kube_node_status_condition{condition="Ready",status="true",node=~"music-store-.*"}'
    url = "http://prometheus.incident-tools.svc:9090/api/v1/query?query=" + quote(query)
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            body = json.loads(response.read().decode())
        found = {}
        for item_row in body.get("data", {}).get("result", []):
            node = item_row.get("metric", {}).get("node", "")
            value = item_row.get("value", [None, "0"])[1]
            if node:
                found[node] = 1 if str(value) == "1" else 0
        return found
    except Exception:
        return None


def host_of(spec: dict) -> str:
    url = spec.get("url") or ""
    if "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0]
        return host.split(":")[0]
    return spec.get("host") or ""


def resolve(host: str) -> str:
    if not host:
        return "-"
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass
    try:
        return socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
    except Exception:
        return "-"


def run_arch(spec: dict) -> tuple[int, int]:
    mode = spec["mode"]
    if mode == "http":
        return check_http(spec.get("url", ""))
    if mode in ("tcp", "kubelet", "node"):
        return check_tcp(spec["host"], int(spec["port"]))
    return 0, 0


def esc(value: object) -> str:
    text = "-" if value in ("", None) else str(value)
    return text.replace("\\", "\\\\").replace("\n", " ").replace('"', "'")


def finish(spec: dict, up: int, ms: int) -> dict:
    row = {key: spec[key] for key in ("id", "title", "kind", "cluster", "namespace", "node", "endpoint", "protocol", "version")}
    row["ip"] = spec.get("ip") or "-"
    row["subtitle"] = SUBTITLE.get(spec["kind"], spec["kind"])
    row["secondarystat"] = spec["protocol"]
    row["up"] = 1 if up else 0
    row["ms"] = ms
    row["health"] = "up" if row["up"] else "down"
    row["color"] = "#3dd68c" if row["up"] else "#ff5d73"
    return row


def labels(row: dict, keys: tuple[str, ...]) -> str:
    return ",".join(f'{key}="{esc(row.get(key, "-"))}"' for key in keys)


NODE_KEYS = (
    "id", "title", "subtitle", "secondarystat", "kind", "cluster", "namespace",
    "node", "ip", "endpoint", "protocol", "version", "health", "color",
)
EDGE_KEYS = ("id", "source", "target", "secondarystat", "protocol", "health", "color")


def refresh() -> None:
    key = os.environ.get("QWEN_API_KEY", "").strip()
    demo: dict[str, tuple[int, int]] = {}
    arch: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        demo_futs = []
        for name, url in CHECKS:
            headers = {"Authorization": "Bearer " + key} if name == "qwen" and key else None
            demo_futs.append((name, pool.submit(one, url, headers)))
        cat_fut = pool.submit(catalog)
        arch_futs = []
        for spec in ARCH:
            if spec["mode"] in ("qwen", "clm"):
                continue
            arch_futs.append((spec, pool.submit(run_arch, spec)))
        ready_fut = pool.submit(music_node_ready)
        for name, fut in demo_futs:
            demo[name] = fut.result()
        demo["catalog"] = (cat_fut.result(), 0)
        ready = ready_fut.result()
        for spec, fut in arch_futs:
            up, ms = fut.result()
            if spec["mode"] == "node" and isinstance(ready, dict) and spec["prom_node"] in ready:
                up = ready[spec["prom_node"]]
            copied = dict(spec)
            if not copied.get("ip"):
                copied["ip"] = resolve(host_of(copied))
            arch[spec["id"]] = finish(copied, up, ms)
    for spec in ARCH:
        if spec["mode"] == "qwen":
            up, ms = demo.get("qwen", (0, 0))
            arch[spec["id"]] = finish(spec, up, ms)
        elif spec["mode"] == "clm":
            up, ms = demo.get("clm", (0, 0))
            copied = dict(spec)
            if not os.environ.get("CLM_URL", "").strip():
                copied["endpoint"] = "not-installed"
                copied["version"] = "not-installed"
                up, ms = 0, 0
            arch[spec["id"]] = finish(copied, up, ms)
    edges = []
    for eid, source, target, protocol in EDGES:
        up = 1 if arch.get(source, {}).get("up") == 1 and arch.get(target, {}).get("up") == 1 else 0
        edges.append({
            "id": eid,
            "source": source,
            "target": target,
            "protocol": protocol,
            "secondarystat": protocol,
            "up": up,
            "health": "up" if up else "down",
            "color": "#3dd68c" if up else "#ff5d73",
        })
    with LOCK:
        STATE["demo"] = demo
        STATE["arch"] = arch
        STATE["edges"] = edges


def loop() -> None:
    while True:
        try:
            refresh()
        except Exception:
            pass
        time.sleep(30)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        with LOCK:
            demo = dict(STATE["demo"])
            arch = dict(STATE["arch"])
            edges = list(STATE["edges"])
        lines = [
            "# HELP demo_up 1 when that demo check succeeded.",
            "# TYPE demo_up gauge",
            "# HELP demo_latency_ms Time the check took.",
            "# TYPE demo_latency_ms gauge",
            "# HELP arch_up 1 when that architecture check succeeded.",
            "# TYPE arch_up gauge",
            "# HELP arch_latency_ms Time the architecture check took.",
            "# TYPE arch_latency_ms gauge",
            "# HELP arch_edge 1 when both ends of a call are up.",
            "# TYPE arch_edge gauge",
        ]
        for name, (up, ms) in sorted(demo.items()):
            lines.append(f'demo_up{{check="{name}"}} {up}')
            lines.append(f'demo_latency_ms{{check="{name}"}} {ms}')
        for row in sorted(arch.values(), key=lambda item_row: item_row["id"]):
            lines.append(f"arch_up{{{labels(row, NODE_KEYS)}}} {row['up']}")
            lines.append(
                f'arch_latency_ms{{id="{esc(row["id"])}",title="{esc(row["title"])}",kind="{esc(row["kind"])}"}} {row["ms"]}'
            )
        for edge in edges:
            lines.append(f"arch_edge{{{labels(edge, EDGE_KEYS)}}} {edge['up']}")
        body = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 9105), Handler).serve_forever()


if __name__ == "__main__":
    main()
