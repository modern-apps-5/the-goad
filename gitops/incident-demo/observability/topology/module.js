define(["react", "@grafana/data"], function (ReactMod, dataMod) {
  "use strict";

  var React = ReactMod && ReactMod.useState ? ReactMod : (ReactMod && ReactMod.default) || ReactMod;
  var gd = dataMod && dataMod.PanelPlugin ? dataMod : (dataMod && dataMod.default) || dataMod;

  var HEALTH = { up: "#3dd68c", down: "#ff5d73", slow: "#f5c16c", unknown: "#64748b" };
  var PROTO = { HTTP: "#79b8ff", HTTPS: "#d2a8ff", TCP: "#e3b341", MCP: "#7ec8c3", OAuth: "#f0a35e" };
  var INK = "#e8eef6";
  var BG = "#070b14";

  // The platform accent is the signal: group outline, header band, and the
  // thin outline of every box inside. Boxes themselves stay the panel color.
  // None of these accents are green or red. Those two stay on the status dot.
  var PLATFORMS = {
    vks: { legend: "VKS", header: "VKS (Kubernetes)", box: "VKS", accent: "#4c8dff", ink: "#b9d4ff" },
    tanzu: { legend: "Tanzu", header: "Tanzu Platform", box: "Tanzu", accent: "#b794f6", ink: "#e0d4ff" },
    vm: { legend: "VM", header: "VM Service", box: "VM", accent: "#f5a524", ink: "#ffd7a1" },
    dsm: { legend: "DSM", header: "DSM", box: "DSM", accent: "#e6c229", ink: "#ffe58a" },
    "private-ai": { legend: "Private AI", header: "Private AI", box: "Private AI", accent: "#e879f9", ink: "#f6c2ff" },
    avi: { legend: "Avi", header: "Avi", box: "Avi", accent: "#2dd4bf", ink: "#9cf3e8" },
    agentminder: { legend: "AgentMinder", header: "AgentMinder", box: "AM", accent: "#f472b6", ink: "#ffc2da" },
    vcf: { legend: "VCF", header: "VCF", box: "VCF", accent: "#94a3b8", ink: "#d5dee8" }
  };
  var KINDS = {
    app: { legend: "app", color: "#8eb4ff" },
    agent: { legend: "agent", color: "#d4b6ff" },
    mcp: { legend: "mcp", color: "#7fd6ea" },
    data: { legend: "data", color: "#f0d060" },
    model: { legend: "model", color: "#f0a0e8" },
    platform: { legend: "platform", color: "#c5d0dc" }
  };
  var PLATFORM_OF = {
    "vks-api": "vks", "cp-pwtc2": "vks", "worker-8n8n5": "vks", "worker-gjwhn": "vks",
    "users-vm": "vm",
    "am-api": "agentminder", "am-cp": "agentminder", "am-w-7dsds": "agentminder", "am-w-gpn6h": "agentminder", "am-ui": "agentminder",
    music: "vks", chat: "vks", cart: "vks", order: "vks", zammad: "vks",
    "zammad-db": "vks", "zammad-redis": "vks", "zammad-cache": "vks", orch: "vks",
    pii: "tanzu", "k8s-mcp": "tanzu", "vcf-mcp": "tanzu", "avi-mcp": "avi",
    dsm: "dsm", qwen: "private-ai", clm: "private-ai",
    incident: "tanzu", "cf-orch": "tanzu", "lb-agent": "tanzu", "k8s-agent": "tanzu", "vcf-agent": "tanzu",
    "vcf-ops": "vcf", vcfa: "vcf", vcenter: "vcf", nsx: "vcf"
  };
  var KIND_OF = {
    "vks-api": "platform", "cp-pwtc2": "platform", "worker-8n8n5": "platform", "worker-gjwhn": "platform",
    "users-vm": "app",
    "am-api": "platform", "am-cp": "platform", "am-w-7dsds": "platform", "am-w-gpn6h": "platform", "am-ui": "platform",
    music: "app", chat: "app", cart: "app", order: "app", pii: "app", zammad: "app",
    "zammad-db": "data", "zammad-redis": "data", "zammad-cache": "data", orch: "agent",
    "k8s-mcp": "mcp", "vcf-mcp": "mcp", "avi-mcp": "mcp",
    dsm: "data", qwen: "model", clm: "model",
    incident: "agent", "cf-orch": "agent", "lb-agent": "agent", "k8s-agent": "agent", "vcf-agent": "agent",
    "vcf-ops": "platform", vcfa: "platform", vcenter: "platform", nsx: "platform"
  };

  // Groups are platforms. Gutters and the top lanes are the wire paths.
  var GEO = {
    zoneY: 108,
    zoneH: 600,
    tz: { x: 16, y: 108, w: 440, h: 600 },
    vm: { x: 468, y: 108, w: 156, h: 600 },
    vks: { x: 636, y: 108, w: 660, h: 600 },
    dsm: { x: 1308, y: 108, w: 148, h: 600 },
    avi: { x: 1468, y: 108, w: 140, h: 600 },
    pai: { x: 1620, y: 108, w: 284, h: 340 },
    am: { x: 1620, y: 460, w: 284, h: 248 },
    vcf: { x: 16, y: 724, w: 1888, h: 340 }
  };

  function meta(id, label, role, icon, mode, cluster, namespace, node, ip, endpoint, version) {
    return {
      id: id, label: label, role: role, icon: icon, mode: mode,
      cluster: cluster, namespace: namespace, node: node, ip: ip,
      endpoint: endpoint, version: version
    };
  }

  var KUBE = "v1.36.2+vmware.2";
  var N8 = "music-store-workers-6xtl4-wnr4j-8n8n5";
  var NG = "music-store-workers-6xtl4-wnr4j-gjwhn";
  var CATALOG = [
    meta("vks-api", "VKS API", "Cluster", "cluster", "wide", "music-store", "music-store-8q8l6", "—", "10.47.7.81", "10.47.7.81:6443", KUBE),
    meta("cp-pwtc2", "Control plane", "Node", "server", "wide", "music-store", "music-store-8q8l6", "music-store-k4sgg-pwtc2", "172.30.0.66", "172.30.0.66:10250", KUBE + " best-effort-medium"),
    meta("worker-8n8n5", "Worker 8n8n5", "Node", "server", "wide", "music-store", "music-store-8q8l6", N8, "172.30.0.70", "172.30.0.70:10250", KUBE + " best-effort-large"),
    meta("worker-gjwhn", "Worker gjwhn", "Node", "server", "wide", "music-store", "music-store-8q8l6", NG, "172.30.0.69", "172.30.0.69:10250", KUBE + " best-effort-large"),
    meta("users-vm", "Users VM", "VM Service", "vm", "vmhost", "music-store", "music-store-8q8l6", "music-users", "10.47.7.52", "http://10.47.7.52:5003/health", "ubuntu-24.04-cloud"),
    meta("am-api", "API", "Cluster", "cluster", "stack", "agentminder", "agentminder-z7v8k", "—", "10.47.7.77", "10.47.7.77:6443", KUBE),
    meta("am-cp", "Control", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-5nprd-9btlg", "172.30.0.34", "172.30.0.34:10250", KUBE),
    meta("am-w-7dsds", "7dsds", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-7dsds", "172.30.0.36", "172.30.0.36:10250", KUBE),
    meta("am-w-gpn6h", "gpn6h", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-gpn6h", "172.30.0.35", "172.30.0.35:10250", KUBE),
    meta("am-ui", "Console", "AgentMinder", "window", "stack", "agentminder", "ssp", "—", "10.47.7.82", "https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/", "console"),
    meta("music", "Music shop", "store", "shop", "wide", "music-store", "music-store", N8, "10.101.76.254", "http://music-store-1-service.music-store.svc:5000/", "python:3.12-slim"),
    meta("chat", "Chat", "assistant", "chat", "wide", "music-store", "music-store", N8, "10.111.73.154", "http://chat-service.music-store.svc:5005/health", "python:3.12-slim"),
    meta("cart", "Cart", "store", "cart", "wide", "music-store", "music-store", N8, "10.97.251.112", "http://cart-service.music-store.svc:5002/health", "python:3.12-slim"),
    meta("order", "Order", "store", "order", "wide", "music-store", "music-store", N8, "10.111.74.18", "http://order-service.music-store.svc:5001/health", "python:3.12-slim"),
    meta("pii", "PII scrub", "filter", "shield", "wide", "music-store", "metal-music-app-agentic-system", NG, "10.105.6.138", "http://pii-scrub.metal-music-app-agentic-system.svc:8080/health", "python:3.12-slim"),
    meta("orch", "Orchestrator", "In cluster", "nodes", "wide", "music-store", "metal-music-app-agentic-system", NG, "10.100.115.123", "http://orchestrator.metal-music-app-agentic-system.svc:8080/health", "python:3.12-slim"),
    meta("zammad", "Zammad", "Tickets", "ticket", "wide", "music-store", "incident-tools", "—", "10.47.7.83", "http://zammad-nginx.incident-tools.svc:8080/", "—"),
    meta("zammad-db", "Postgres", "Database", "db", "wide", "music-store", "incident-tools", "—", "10.106.205.2", "zammad-postgresql.incident-tools.svc:5432", "—"),
    meta("zammad-redis", "Redis", "Cache", "layers", "wide", "music-store", "incident-tools", "—", "10.97.122.51", "zammad-redis.incident-tools.svc:6379", "—"),
    meta("zammad-cache", "Memcached", "Cache", "box", "wide", "music-store", "incident-tools", "—", "10.109.25.157", "zammad-memcached.incident-tools.svc:11211", "—"),
    meta("dsm", "Catalog", "Postgres 16.14", "db", "feature", "music-store", "music-store-8q8l6", "—", "10.47.7.78", "10.47.7.78:5432", "16.14+vmware.v9.1.1.0"),
    meta("qwen", "Qwen", "qwen-14b-xlarge", "chip", "feature", "private-ai", "private-ai-hphfz", "—", "10.47.7.73", "https://10.47.7.73", "qwen-14b-xlarge"),
    meta("clm", "CLM", "Not installed", "chip", "feature", "private-ai", "—", "—", "—", "not-installed", "not-installed"),
    meta("incident", "Incident", "Agent", "bot", "wide", "tanzu-cf", "metal-music-app-agentic-system", "—", "—", "https://incident-response-agent.apps.tp.gpu.set.lab/health", "tanzu-agent 0.6.0"),
    meta("cf-orch", "Orchestrator", "Agent", "nodes", "wide", "tanzu-cf", "metal-music-app-agentic-system", "—", "—", "https://metal-incident-live.apps.tp.gpu.set.lab/health", "harness.py"),
    meta("lb-agent", "Load balancer", "Agent", "bot", "wide", "tanzu-cf", "metal-music-app-agentic-system", "—", "—", "https://lb-diagnostic-agent.apps.tp.gpu.set.lab/health", "tanzu-agent 0.6.0"),
    meta("k8s-agent", "Kubernetes", "Agent", "bot", "wide", "tanzu-cf", "metal-music-app-agentic-system", "—", "—", "https://k8s-diagnostic-agent.apps.tp.gpu.set.lab/health", "tanzu-agent 0.6.0"),
    meta("vcf-agent", "VCF", "Agent", "bot", "wide", "tanzu-cf", "metal-music-app-agentic-system", "—", "—", "https://vcf-diagnostic-agent.apps.tp.gpu.set.lab/health", "tanzu-agent 0.6.0"),
    meta("avi-mcp", "Avi", "MCP server", "plug", "wide", "music-store", "metal-music-app-agentic-system", NG, "10.47.7.68", "http://avi-mcp.goad.gpu.set.lab/mcp", "python:3.12-slim"),
    meta("k8s-mcp", "Kubernetes", "MCP server", "plug", "wide", "music-store", "metal-music-app-agentic-system", N8, "10.47.7.85", "http://k8s-mcp.goad.gpu.set.lab/mcp", "python:3.12-slim"),
    meta("vcf-mcp", "VCF", "MCP server", "plug", "wide", "music-store", "metal-music-app-agentic-system", NG, "10.47.7.86", "http://vcf-mcp.goad.gpu.set.lab/mcp", "python:3.12-slim"),
    meta("vcf-ops", "VCF Ops", "ops01", "pulse", "wide", "vcf", "ops01", "—", "10.47.0.221", "10.47.0.221:443", "ops01.gpu.set.lab"),
    meta("vcfa", "VCFA", "Automation", "window", "wide", "vcf", "auto", "—", "10.47.0.224", "10.47.0.224:443", "auto.gpu.set.lab"),
    meta("vcenter", "vCenter", "vc01", "server", "wide", "vcf", "vc01", "—", "10.47.0.200", "10.47.0.200:443", "vc01.gpu.set.lab"),
    meta("nsx", "NSX", "nsx01", "layers", "wide", "vcf", "nsx01", "—", "10.47.0.230", "10.47.0.230:443", "nsx01.gpu.set.lab")
  ];

  var EDGES = [
    ["e-music-vm", "music", "users-vm", "HTTP"],
    ["e-music-chat", "music", "chat", "HTTP"],
    ["e-music-cart", "music", "cart", "HTTP"],
    ["e-music-order", "music", "order", "HTTP"],
    ["e-music-dsm", "music", "dsm", "TCP 5432"],
    ["e-chat-order", "chat", "order", "HTTP"],
    ["e-chat-dsm", "chat", "dsm", "TCP 5432"],
    ["e-chat-qwen", "chat", "qwen", "HTTPS"],
    ["e-incident-orch", "incident", "cf-orch", "HTTP"],
    ["e-incident-zammad", "incident", "zammad", "HTTPS"],
    ["e-cforch-lb", "cf-orch", "lb-agent", "HTTP"],
    ["e-cforch-k8s", "cf-orch", "k8s-agent", "HTTP"],
    ["e-cforch-vcf", "cf-orch", "vcf-agent", "HTTP"],
    ["e-cforch-zammad", "cf-orch", "zammad", "HTTPS"],
    ["e-cforch-qwen", "cf-orch", "qwen", "HTTPS"],
    ["e-lb-avi", "lb-agent", "avi-mcp", "MCP"],
    ["e-k8s-mcp", "k8s-agent", "k8s-mcp", "MCP"],
    ["e-vcf-mcp", "vcf-agent", "vcf-mcp", "MCP"],
    ["e-lb-am", "lb-agent", "am-ui", "OAuth"],
    ["e-k8s-am", "k8s-agent", "am-ui", "OAuth"],
    ["e-vcf-am", "vcf-agent", "am-ui", "OAuth"],
    ["e-lb-qwen", "lb-agent", "qwen", "HTTPS"],
    ["e-k8s-qwen", "k8s-agent", "qwen", "HTTPS"],
    ["e-vcf-qwen", "vcf-agent", "qwen", "HTTPS"],
    ["e-orch-qwen", "orch", "qwen", "HTTPS"],
    ["e-orch-music", "orch", "music", "HTTP"],
    ["e-zammad-db", "zammad", "zammad-db", "TCP 5432"],
    ["e-zammad-redis", "zammad", "zammad-redis", "TCP 6379"],
    ["e-zammad-cache", "zammad", "zammad-cache", "TCP 11211"]
  ];

  var BY_ID = {};
  CATALOG.forEach(function (n) {
    n.platform = PLATFORM_OF[n.id] || "vks";
    n.kind = KIND_OF[n.id] || "app";
    BY_ID[n.id] = n;
  });

  function pack(ids, zoneX, zoneW, y, h, cardW, gap, into) {
    var total = ids.length * cardW + (ids.length - 1) * gap;
    var x = zoneX + Math.round((zoneW - total) / 2);
    ids.forEach(function (id, i) {
      into[id] = Object.assign({ x: x + i * (cardW + gap), y: y, w: cardW, h: h }, BY_ID[id]);
    });
  }

  function place(nodes, id, x, y, w, h, extra) {
    nodes[id] = Object.assign({}, BY_ID[id], {
      x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h)
    }, extra || {});
  }

  function row(nodes, ids, x0, y, w, h, gap, extra) {
    ids.forEach(function (id, i) {
      place(nodes, id, x0 + i * (w + gap), y, w, h, extra);
    });
  }

  function grid(nodes, ids, x0, y0, cols, w, h, gx, gy) {
    ids.forEach(function (id, i) {
      var c = i % cols;
      var r = Math.floor(i / cols);
      place(nodes, id, x0 + c * (w + gx), y0 + r * (h + gy), w, h);
    });
  }

  function zoneOf(key, mark) {
    var g = GEO[key];
    var plat = PLATFORMS[key === "pai" ? "private-ai" : key === "am" ? "agentminder" : key === "tz" ? "tanzu" : key];
    return {
      id: key, title: plat.header, mark: mark, accent: plat.accent, ink: plat.ink,
      x: g.x, y: g.y, w: g.w, h: g.h
    };
  }

  function layout() {
    var nodes = {};
    grid(nodes, ["incident", "cf-orch", "lb-agent", "k8s-agent", "vcf-agent", "pii", "k8s-mcp", "vcf-mcp"], 30, 148, 2, 201, 120, 10, 10);
    place(nodes, "users-vm", 482, 156, 128, 100);
    row(nodes, ["music", "chat", "cart", "order"], 650, 148, 152, 112, 8);
    row(nodes, ["zammad", "zammad-db", "zammad-redis", "zammad-cache"], 650, 272, 152, 112, 8);
    place(nodes, "orch", 650, 396, 152, 112);
    row(nodes, ["vks-api", "cp-pwtc2", "worker-8n8n5", "worker-gjwhn"], 650, 520, 152, 112, 8);
    place(nodes, "dsm", 1320, 156, 124, 200);
    place(nodes, "avi-mcp", 1482, 200, 112, 160);
    place(nodes, "qwen", 1636, 156, 252, 130);
    place(nodes, "clm", 1636, 300, 252, 128);
    row(nodes, ["am-api", "am-cp", "am-ui"], 1632, 508, 80, 90, 8);
    row(nodes, ["am-w-7dsds", "am-w-gpn6h"], 1632, 606, 80, 90, 8);
    var fw = 420;
    var fg = 24;
    var f0 = 16 + Math.round((1888 - (4 * fw + 3 * fg)) / 2);
    row(nodes, ["vcf-ops", "vcfa", "vcenter", "nsx"], f0, 800, fw, 180, fg);

    var zones = ["tz", "vm", "vks", "dsm", "avi", "pai", "am", "vcf"].map(function (key) {
      var mark = { tz: "tanzu", vm: "vm", vks: "vks", dsm: "dsm", avi: "avi", pai: "pai", am: "agentminder", vcf: "vcf" }[key];
      return zoneOf(key, mark);
    });
    return { zones: zones, nodes: nodes };
  }

  function mx(n) { return n.x + n.w / 2; }
  function my(n) { return n.y + n.h / 2; }

  function hlink(a, b) {
    var y = Math.round((my(a) + my(b)) / 2);
    if (a.x <= b.x) return [[a.x + a.w, y], [b.x, y]];
    return [[a.x, y], [b.x + b.w, y]];
  }

  function rail(a, b, y, leave, enter) {
    var x1 = mx(a);
    var x2 = mx(b);
    var y1 = leave === "s" ? a.y + a.h : a.y;
    var y2 = enter === "s" ? b.y + b.h : b.y;
    return [[x1, y1], [x1, y], [x2, y], [x2, y2]];
  }

  function buildRoutes(N) {
    var R = {};
    function add(id, pts) { R[id] = pts; }
    function cx(n) { return mx(n); }
    function cy(n) { return my(n); }
    function L(n) { return n.x; }
    function Rt(n) { return n.x + n.w; }
    function T(n) { return n.y; }
    function B(n) { return n.y + n.h; }
    var sky = [58, 63, 68, 73, 78, 88, 93, 98, 103];
    var leftX = 8;
    var rightX = 1912;
    var gT = GEO.tz.x + GEO.tz.w + (GEO.vm.x - (GEO.tz.x + GEO.tz.w)) / 2;

    add("e-incident-orch", hlink(N.incident, N["cf-orch"]));
    add("e-music-chat", hlink(N.music, N.chat));
    add("e-zammad-db", hlink(N.zammad, N["zammad-db"]));
    add("e-cforch-k8s", [
      [cx(N["cf-orch"]), B(N["cf-orch"])],
      [cx(N["k8s-agent"]), T(N["k8s-agent"])]
    ]);

    var yT01 = Math.round((B(N.incident) + T(N["lb-agent"])) / 2);
    add("e-cforch-lb", [
      [cx(N["cf-orch"]), B(N["cf-orch"])],
      [cx(N["cf-orch"]), yT01],
      [cx(N["lb-agent"]), yT01],
      [cx(N["lb-agent"]), T(N["lb-agent"])]
    ]);
    var yT12 = Math.round((B(N["lb-agent"]) + T(N["vcf-agent"])) / 2);
    add("e-cforch-vcf", [
      [Rt(N["cf-orch"]), cy(N["cf-orch"])],
      [gT, cy(N["cf-orch"])],
      [gT, yT12],
      [cx(N["vcf-agent"]), yT12],
      [cx(N["vcf-agent"]), T(N["vcf-agent"])]
    ]);
    var yT23 = Math.round((B(N["vcf-agent"]) + T(N["k8s-mcp"])) / 2);
    add("e-k8s-mcp", [
      [Rt(N["k8s-agent"]), cy(N["k8s-agent"])],
      [gT, cy(N["k8s-agent"])],
      [gT, yT23],
      [cx(N["k8s-mcp"]), yT23],
      [cx(N["k8s-mcp"]), T(N["k8s-mcp"])]
    ]);
    add("e-vcf-mcp", [
      [cx(N["vcf-agent"]), B(N["vcf-agent"])],
      [cx(N["vcf-agent"]), yT23],
      [cx(N["vcf-mcp"]), yT23],
      [cx(N["vcf-mcp"]), T(N["vcf-mcp"])]
    ]);

    var yShop = Math.round((B(N.music) + T(N.zammad)) / 2);
    add("e-music-cart", [
      [cx(N.music), B(N.music)],
      [cx(N.music), yShop - 4],
      [cx(N.cart), yShop - 4],
      [cx(N.cart), B(N.cart)]
    ]);
    add("e-music-order", [
      [cx(N.music), B(N.music)],
      [cx(N.music), yShop],
      [cx(N.order), yShop],
      [cx(N.order), B(N.order)]
    ]);
    add("e-chat-order", [
      [cx(N.chat), B(N.chat)],
      [cx(N.chat), yShop],
      [cx(N.order), yShop],
      [cx(N.order), B(N.order)]
    ]);
    add("e-music-dsm", [
      [cx(N.music), B(N.music)],
      [cx(N.music), yShop - 4],
      [L(N.dsm), yShop - 4]
    ]);
    add("e-chat-dsm", [
      [cx(N.chat), B(N.chat)],
      [cx(N.chat), yShop + 2],
      [L(N.dsm), yShop + 2]
    ]);

    var yBus = 270;
    add("e-incident-zammad", [
      [cx(N.incident), B(N.incident)],
      [cx(N.incident), yBus],
      [cx(N.zammad) - 14, yBus],
      [cx(N.zammad) - 14, T(N.zammad)]
    ]);
    add("e-cforch-zammad", [
      [cx(N["cf-orch"]), B(N["cf-orch"])],
      [cx(N["cf-orch"]), yBus],
      [cx(N.zammad) + 14, yBus],
      [cx(N.zammad) + 14, T(N.zammad)]
    ]);
    add("e-music-vm", [
      [Rt(N["users-vm"]), cy(N.music)],
      [L(N.music), cy(N.music)]
    ]);

    var yData = Math.round((B(N.zammad) + T(N.orch)) / 2);
    add("e-zammad-redis", [
      [cx(N.zammad), B(N.zammad)],
      [cx(N.zammad), yData - 3],
      [cx(N["zammad-redis"]), yData - 3],
      [cx(N["zammad-redis"]), B(N["zammad-redis"])]
    ]);
    add("e-zammad-cache", [
      [cx(N.zammad), B(N.zammad)],
      [cx(N.zammad), yData + 3],
      [cx(N["zammad-cache"]), yData + 3],
      [cx(N["zammad-cache"]), B(N["zammad-cache"])]
    ]);

    var pad = N.music.x - 8;
    add("e-orch-music", [
      [L(N.orch), cy(N.orch)],
      [pad, cy(N.orch)],
      [pad, cy(N.music)],
      [L(N.music), cy(N.music)]
    ]);
    add("e-orch-qwen", [
      [Rt(N.orch), cy(N.orch)],
      [rightX, cy(N.orch)],
      [rightX, cy(N.qwen)],
      [Rt(N.qwen), cy(N.qwen)]
    ]);

    function skyFrom(node, lane, exit) {
      if (exit === "n") return [[cx(node), T(node)], [cx(node), lane]];
      if (exit === "w") return [[L(node), cy(node)], [leftX, cy(node)], [leftX, lane]];
      return [[Rt(node), cy(node)], [gT, cy(node)], [gT, lane]];
    }
    function overTop(id, node, lane, dropX, targetTop, exit) {
      var pts = skyFrom(node, lane, exit);
      pts.push([dropX, lane], [dropX, targetTop]);
      add(id, pts);
    }
    var q = N.qwen;
    overTop("e-cforch-qwen", N["cf-orch"], sky[0], 1765, T(q), "n");
    overTop("e-lb-qwen", N["lb-agent"], sky[1], 1795, T(q), "w");
    overTop("e-k8s-qwen", N["k8s-agent"], sky[2], 1825, T(q), "e");
    overTop("e-vcf-qwen", N["vcf-agent"], sky[3], 1855, T(q), "w");
    overTop("e-chat-qwen", N.chat, sky[4], 1878, T(q), "n");
    overTop("e-lb-avi", N["lb-agent"], sky[5], 1570, T(N["avi-mcp"]), "w");

    function toAm(id, node, lane, entryY, exit) {
      var pts = skyFrom(node, lane, exit);
      pts.push([rightX, lane], [rightX, entryY], [Rt(N["am-ui"]), entryY]);
      add(id, pts);
    }
    toAm("e-lb-am", N["lb-agent"], sky[6], cy(N["am-ui"]) - 16, "w");
    toAm("e-k8s-am", N["k8s-agent"], sky[7], cy(N["am-ui"]), "e");
    toAm("e-vcf-am", N["vcf-agent"], sky[8], cy(N["am-ui"]) + 16, "w");
    return R;
  }

  function badge(name, color) {
    var s = ' fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"';
    var f = ' fill="' + color + '" stroke="none"';
    var paths = {
      vks: '<polygon points="9,1.4 16,5.2 16,12.8 9,16.6 2,12.8 2,5.2"' + s + '/><circle cx="9" cy="9" r="1.6"' + f + '/><circle cx="9" cy="4.6" r="1"' + f + '/><circle cx="5" cy="12.2" r="1"' + f + '/><circle cx="13" cy="12.2" r="1"' + f + '/>',
      tanzu: '<path d="M2.2 13.6 9 3.4 15.8 13.6"' + s + '/><path d="M4.6 13.6 9 7.4 13.4 13.6"' + s + '/>',
      dsm: '<ellipse cx="9" cy="4.4" rx="6" ry="2.1"' + s + '/><path d="M3 4.4v8.8c0 1.2 2.7 2.3 6 2.3s6-1.1 6-2.3V4.4"' + s + '/><path d="M3 8.8c0 1.2 2.7 2.2 6 2.2s6-1 6-2.2"' + s + '/>',
      vcf: '<rect x="1.6" y="1.6" width="6.2" height="6.2" rx="1.4"' + s + '/><rect x="10.2" y="1.6" width="6.2" height="6.2" rx="1.4"' + s + '/><rect x="1.6" y="10.2" width="6.2" height="6.2" rx="1.4"' + s + '/><rect x="10.2" y="10.2" width="6.2" height="6.2" rx="1.4"' + s + '/>',
      agentminder: '<rect x="2" y="2.4" width="14" height="13.2" rx="3"' + s + '/><circle cx="9" cy="8.2" r="2.2"' + s + '/><path d="M6.2 13.2c.6-1.5 1.6-2.2 2.8-2.2s2.2.7 2.8 2.2"' + s + '/>',
      pai: '<rect x="5.2" y="5.2" width="7.6" height="7.6" rx="1.5"' + s + '/><path d="M7.4 2v2.4M10.6 2v2.4M7.4 13.6V16M10.6 13.6V16M2 7.4h2.4M2 10.6h2.4M13.6 7.4H16M13.6 10.6H16"' + s + '/>',
      vm: '<rect x="2" y="3.2" width="14" height="9" rx="1.4"' + s + '/><path d="M6 15.4h6M9 12.2v3.2"' + s + '/>',
      avi: '<path d="M1.8 11.6h14.4M9 11.6V4.4M4.6 6.6 9 4.4l4.4 2.2"' + s + '/>'
    };
    return paths[name] || "";
  }

  function icon(name, color) {
    color = color || "#d7e2f0";
    var s = ' fill="none" stroke="' + color + '" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"';
    var f = ' fill="' + color + '" stroke="none"';
    var paths = {
      cluster: '<polygon points="12,2.4 20.8,7.4 20.8,16.6 12,21.6 3.2,16.6 3.2,7.4"' + s + '/><circle cx="12" cy="12" r="2.1"' + f + '/>',
      server: '<rect x="5" y="3" width="14" height="18" rx="2"' + s + '/><path d="M8 7.5h8M8 11.5h8M8 15.5h4"' + s + '/><circle cx="15.2" cy="16.6" r="1"' + f + '/>',
      vm: '<rect x="3" y="4" width="18" height="12" rx="2"' + s + '/><path d="M8 20h8M12 16v4"' + s + '/>',
      user: '<circle cx="12" cy="8" r="3"' + s + '/><path d="M5.5 19.2c1.2-3.2 3.5-4.7 6.5-4.7s5.3 1.5 6.5 4.7"' + s + '/>',
      db: '<ellipse cx="12" cy="6.5" rx="7" ry="2.6"' + s + '/><path d="M5 6.5v11c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7v-11"' + s + '/><path d="M5 12c0 1.5 3.1 2.7 7 2.7s7-1.2 7-2.7"' + s + '/>',
      shop: '<path d="M4 10h16v8.2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V10z"' + s + '/><path d="M3.5 10 6.2 4.8h11.6L20.5 10"' + s + '/><path d="M9 14h6"' + s + '/>',
      chat: '<path d="M5 5.5h14a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H9.2L5 18.2V6.5a1 1 0 0 1 1-1z"' + s + '/>',
      cart: '<path d="M4.5 6h2.2l1.4 9.2h8.8"' + s + '/><path d="M8 8.2h11.2L18 13.2H8.4"' + s + '/><circle cx="10" cy="18.2" r="1.25"' + f + '/><circle cx="16" cy="18.2" r="1.25"' + f + '/>',
      order: '<path d="M7 3.5h8l3 3V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1z"' + s + '/><path d="M14.5 3.8V7H18M8.5 11h7M8.5 14.5h7M8.5 17.5h4"' + s + '/>',
      pulse: '<path d="M3 12h3.5l2.2-5 3.6 10 2.2-5H21"' + s + '/>',
      shield: '<path d="M12 3.2 19 6.2v5.4c0 3.8-2.7 6.4-7 8.2-4.3-1.8-7-4.4-7-8.2V6.2L12 3.2z"' + s + '/><path d="M9 12.1 11.1 14.2 15.3 10"' + s + '/>',
      ticket: '<path d="M4 8.5a2 2 0 0 0 2-2h12a2 2 0 0 0 2 2 2 2 0 0 0-2 2H6a2 2 0 0 0-2-2z" transform="translate(0 3)"' + s + '/><path d="M3.5 7h17v10h-17z"' + s + '/><path d="M12 7v10"' + s + '/>',
      layers: '<path d="M12 4 20 8.2 12 12.4 4 8.2Z"' + s + '/><path d="M4 12.2 12 16.4 20 12.2"' + s + '/><path d="M4 16 12 20.2 20 16"' + s + '/>',
      box: '<rect x="4" y="4" width="16" height="16" rx="2"' + s + '/><path d="M4 9h16M9 9v11"' + s + '/>',
      nodes: '<circle cx="6.5" cy="8" r="2.2"' + s + '/><circle cx="17" cy="7" r="2.2"' + s + '/><circle cx="12" cy="17" r="2.2"' + s + '/><path d="M8.4 9.2 10.6 15.2M15.1 8.8 13.2 15"' + s + '/>',
      chip: '<rect x="7" y="7" width="10" height="10" rx="2"' + s + '/><path d="M9.5 3.2v3.8M12 3.2v3.8M14.5 3.2v3.8M9.5 17v3.8M12 17v3.8M14.5 17v3.8M3.2 9.5H7M3.2 12H7M3.2 14.5H7M17 9.5h3.8M17 12h3.8M17 14.5h3.8"' + s + '/>',
      window: '<rect x="3" y="4" width="18" height="16" rx="2"' + s + '/><path d="M3 8.5h18M8 8.5V20"' + s + '/>',
      bot: '<rect x="5" y="8" width="14" height="10" rx="3"' + s + '/><circle cx="9.5" cy="13" r="1.15"' + f + '/><circle cx="14.5" cy="13" r="1.15"' + f + '/><path d="M12 8V4.6"' + s + '/><circle cx="12" cy="3.5" r="1"' + f + '/>',
      plug: '<path d="M9 8.5V4M15 8.5V4"' + s + '/><rect x="6" y="8.5" width="12" height="6" rx="2"' + s + '/><path d="M12 14.5v2.8a2.6 2.6 0 0 1-2.6 2.6H8"' + s + '/>'
    };
    return paths[name] || paths.box;
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function clean(pts) {
    var out = [];
    pts.forEach(function (p) {
      var q = [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
      var prev = out[out.length - 1];
      if (!prev || Math.abs(prev[0] - q[0]) > 0.4 || Math.abs(prev[1] - q[1]) > 0.4) out.push(q);
    });
    return out;
  }

  function pathOf(pts) {
    pts = clean(pts);
    if (pts.length < 2) return "";
    var r = 12;
    var d = "M " + pts[0][0] + " " + pts[0][1];
    for (var i = 1; i < pts.length - 1; i++) {
      var a = pts[i - 1], b = pts[i], c = pts[i + 1];
      var v1x = b[0] - a[0], v1y = b[1] - a[1];
      var v2x = c[0] - b[0], v2y = c[1] - b[1];
      var l1 = Math.hypot(v1x, v1y), l2 = Math.hypot(v2x, v2y);
      if (l1 < 1 || l2 < 1) continue;
      var rr = Math.min(r, l1 / 2, l2 / 2);
      var ax = b[0] - (v1x / l1) * rr, ay = b[1] - (v1y / l1) * rr;
      var bx = b[0] + (v2x / l2) * rr, by = b[1] + (v2y / l2) * rr;
      d += " L " + ax.toFixed(1) + " " + ay.toFixed(1) + " Q " + b[0] + " " + b[1] + " " + bx.toFixed(1) + " " + by.toFixed(1);
    }
    d += " L " + pts[pts.length - 1][0] + " " + pts[pts.length - 1][1];
    return d;
  }

  function lengthOf(pts) {
    var n = 0;
    for (var i = 1; i < pts.length; i++) n += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    return n;
  }

  function protoColor(p) {
    var s = String(p || "");
    if (s.indexOf("HTTPS") === 0) return PROTO.HTTPS;
    if (s.indexOf("HTTP") === 0) return PROTO.HTTP;
    if (s.indexOf("TCP") === 0) return PROTO.TCP;
    if (s.indexOf("MCP") === 0) return PROTO.MCP;
    if (s.indexOf("OAuth") === 0) return PROTO.OAuth;
    return "#8b9cb8";
  }

  function blank(v) {
    return v == null || v === "" || v === "-" || v === "—" || v === "None";
  }

  function pick(live, fallback) {
    return blank(live) ? (blank(fallback) ? "" : String(fallback)) : String(live);
  }

  function stateOf(value, latency) {
    if (value == null || value === "") return "unknown";
    if (Number(value) !== 1) return "down";
    if (latency != null && Number(latency) >= 800) return "slow";
    return "up";
  }

  function at(field, i) {
    var v = field && field.values;
    if (!v) return undefined;
    if (typeof v.get === "function") return v.get(i);
    return v[i];
  }

  function flen(field) {
    var v = field && field.values;
    if (!v) return 0;
    return typeof v.length === "number" ? v.length : 0;
  }

  function isValueField(name) {
    return name === "Value" || name.indexOf("Value ") === 0 || name === "arch_up" || name === "arch_edge" || name === "arch_latency_ms";
  }

  function readSeries(data) {
    var series = (data && data.series) || data || [];
    var nodes = {}, edges = {}, lats = {};
    series.forEach(function (frame) {
      var fields = frame.fields || [];
      var n = frame.length || 0;
      fields.forEach(function (f) { n = Math.max(n, flen(f)); });
      for (var i = 0; i < n; i++) {
        var row = {};
        fields.forEach(function (f) {
          if (f.labels) {
            Object.keys(f.labels).forEach(function (k) { row[k] = f.labels[k]; });
          }
          if (!f.name || f.name === "Time") return;
          var val = at(f, i);
          if (isValueField(f.name) || f.type === "number") {
            row.value = val;
          } else if (val != null) {
            row[f.name] = val;
          }
        });
        if (!row.id) continue;
        var dest = edges;
        if (row.source) dest = edges;
        else if (row.cluster || row.endpoint || row.ip || row.health) dest = nodes;
        else if (frame.refId === "C" || (row.kind && !row.source)) dest = lats;
        else if (frame.refId === "A") dest = nodes;
        else if (frame.refId === "B") dest = edges;
        else dest = nodes;
        dest[row.id] = Object.assign(dest[row.id] || {}, row);
      }
    });
    return { nodes: nodes, edges: edges, lats: lats };
  }

  function compose(parsed) {
    var nodes = {};
    CATALOG.forEach(function (n) {
      var live = (parsed.nodes && parsed.nodes[n.id]) || {};
      var lat = parsed.lats && parsed.lats[n.id];
      var latency = lat && lat.value != null && lat.value !== "" ? Number(lat.value) : null;
      nodes[n.id] = {
        label: n.label,
        role: n.role,
        platform: n.platform,
        kind: n.kind,
        cluster: pick(live.cluster, n.cluster),
        namespace: pick(live.namespace, n.namespace),
        node: pick(live.node, n.node),
        ip: pick(live.ip, n.ip),
        endpoint: pick(live.endpoint, n.endpoint),
        version: pick(live.version, n.version),
        title: pick(live.title, n.label),
        value: live.value,
        latency: latency,
        state: stateOf(live.value, latency)
      };
    });
    var edges = {};
    EDGES.forEach(function (e) {
      var live = (parsed.edges && parsed.edges[e[0]]) || {};
      var value = live.value;
      if (value == null || value === "") {
        var a = nodes[e[1]].state;
        var b = nodes[e[2]].state;
        if (a === "down" || b === "down") value = 0;
        else if (a === "up" && b === "up") value = 1;
      }
      edges[e[0]] = {
        id: e[0], source: e[1], target: e[2],
        protocol: pick(live.protocol, e[3]),
        value: value,
        state: value == null || value === "" ? "unknown" : (Number(value) === 1 ? "up" : "down")
      };
    });
    return { nodes: nodes, edges: edges };
  }

  function stampOf(model) {
    var s = [];
    Object.keys(model.nodes).sort().forEach(function (id) {
      var n = model.nodes[id];
      s.push(id + "=" + n.state + ":" + n.latency);
    });
    Object.keys(model.edges).sort().forEach(function (id) {
      s.push(id + "=" + model.edges[id].state);
    });
    return s.join("|");
  }

  function demo() {
    var nodes = {}, edges = {}, lats = {};
    CATALOG.forEach(function (n) {
      var down = n.id === "shop-users" || n.id === "clm";
      nodes[n.id] = { value: down ? 0 : 1, title: n.label };
      lats[n.id] = { value: n.id === "qwen" ? 42 : 16 };
    });
    EDGES.forEach(function (e) {
      edges[e[0]] = { value: e[0] === "e-music-users" ? 0 : 1, protocol: e[3], source: e[1], target: e[2] };
    });
    return compose({ nodes: nodes, edges: edges, lats: lats });
  }

  var PLACED = layout();
  var ROUTES = buildRoutes(PLACED.nodes);

  function buildSvg(model) {
    var parts = [];
    parts.push('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1920 1080" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">');
    parts.push('<defs>');
    parts.push('<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.7" fill="rgba(255,255,255,0.035)"/></pattern>');
    parts.push('<marker id="chev" viewBox="0 0 8 8" refX="6.2" refY="4" markerWidth="4" markerHeight="4" orient="auto"><path d="M1.6 1.8 L6.2 4 L1.6 6.2" fill="none" stroke="context-stroke" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></marker>');
    parts.push('<style>text{font-family:Inter,Segoe UI,system-ui,sans-serif;font-weight:400}</style>');
    parts.push('</defs>');
    parts.push('<rect width="1920" height="1080" fill="' + BG + '"/>');
    parts.push('<rect width="1920" height="1080" fill="url(#dots)"/>');

    function paint(x, y, anchor, fill, size, weight, value) {
      return '<text x="' + x + '" y="' + y + '" text-anchor="' + anchor + '" fill="' + fill + '" font-size="' + size + '" font-weight="' + weight + '">' + esc(value) + '</text>';
    }

    PLACED.zones.forEach(function (z) {
      var clip = "clip-" + z.id;
      parts.push('<clipPath id="' + clip + '"><rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="' + z.h + '" rx="14"/></clipPath>');
      parts.push('<rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="' + z.h + '" rx="14" fill="' + BG + '" fill-opacity="0.25" stroke="' + z.accent + '" stroke-width="1.5"/>');
      parts.push('<g clip-path="url(#' + clip + ')"><rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="30" fill="' + z.accent + '" fill-opacity="0.20"/></g>');
      var tx = z.x + 12;
      if (z.mark) {
        parts.push('<g transform="translate(' + (z.x + 10) + ' ' + (z.y + 7) + ')">' + badge(z.mark, z.ink) + '</g>');
        tx = z.x + 32;
      }
      parts.push(paint(tx, z.y + 20, "start", z.ink, 14, "500", z.title));
    });

    var drawn = [];
    EDGES.forEach(function (e) {
      var edge = model.edges[e[0]];
      var pts = ROUTES[e[0]];
      if (!pts) return;
      drawn.push({ id: e[0], pts: pts, edge: edge, color: protoColor(edge.protocol), len: lengthOf(pts) });
    });
    drawn.sort(function (a, b) {
      if (a.edge.state === "down") return 1;
      if (b.edge.state === "down") return -1;
      return 0;
    });
    drawn.forEach(function (item, index) {
      var d = pathOf(item.pts);
      var down = item.edge.state === "down";
      var unknown = item.edge.state === "unknown";
      var color = down ? HEALTH.down : (unknown ? "#5c6b82" : item.color);
      var dash = down ? ' stroke-dasharray="4 5"' : (unknown ? ' stroke-dasharray="1.5 4"' : "");
      var marker = item.len > 48 && !unknown ? ' marker-end="url(#chev)"' : "";
      var opacity = down ? "0.55" : "0.34";
      parts.push('<path id="p-' + item.id + '" d="' + d + '" fill="none" stroke="' + color + '" stroke-width="1.05" stroke-linecap="round" stroke-linejoin="round" opacity="' + opacity + '"' + dash + marker + '/>');
      parts.push('<path data-k="e:' + item.id + '" d="' + d + '" fill="none" stroke="transparent" stroke-width="12" style="cursor:pointer"/>');
      if (!down && !unknown) {
        var dur = Math.max(2.8, Math.min(8, item.len / 140)).toFixed(1);
        var begin = ((index % 7) * 0.35).toFixed(2);
        parts.push('<circle r="2" fill="' + color + '" opacity="0.7"><animateMotion dur="' + dur + 's" begin="' + begin + 's" repeatCount="indefinite" rotate="auto"><mpath href="#p-' + item.id + '" xlink:href="#p-' + item.id + '"/></animateMotion></circle>');
      }
    });

    CATALOG.forEach(function (spec) {
      var n = PLACED.nodes[spec.id];
      if (!n) return;
      var info = model.nodes[spec.id];
      var color = HEALTH[info.state] || HEALTH.unknown;
      var plat = PLATFORMS[n.platform] || PLATFORMS.vks;
      var kind = KINDS[n.kind] || KINDS.app;
      var down = info.state === "down";
      var titleFill = down ? "#8e9aab" : INK;
      var platFill = down ? "#7d8b9e" : plat.ink;
      var kindFill = down ? "#6e7d90" : "#b7c3d4";
      var titleSize = n.w >= 300 ? 16 : (n.w >= 140 ? 15 : 14);
      var platLabel = plat.box === "AM" && n.w >= 78 ? "AgentMinder" : plat.box;
      var kindLabel = kind.legend;
      parts.push('<g data-k="n:' + spec.id + '" style="cursor:pointer">');
      parts.push('<rect x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="10" fill="' + BG + '" stroke="' + plat.accent + '" stroke-width="1.5" stroke-opacity="' + (down ? "0.4" : "1") + '"/>');
      var dot = n.w >= 200 ? 4.5 : 3.5;
      parts.push('<circle cx="' + (n.x + n.w - dot - 7) + '" cy="' + (n.y + dot + 7) + '" r="' + dot + '" fill="' + color + '"/>');
      if (n.w >= 300) {
        var titleY = n.y + Math.round(n.h / 2) - 4;
        parts.push(paint(n.x + 22, titleY, "start", titleFill, titleSize, "500", n.label));
        parts.push(paint(n.x + 22, titleY + 22, "start", platFill, 11, "400", platLabel));
        var kx = n.x + 22 + Math.round(platLabel.length * 6.4) + 16;
        parts.push('<circle cx="' + kx + '" cy="' + (titleY + 18) + '" r="3" fill="' + kind.color + '"/>');
        parts.push(paint(kx + 8, titleY + 22, "start", kindFill, 11, "400", kindLabel));
      } else if (n.w < 100) {
        parts.push(paint(n.x + 8, n.y + 32, "start", titleFill, titleSize, "500", n.label));
        parts.push(paint(n.x + 8, n.y + 48, "start", platFill, 10, "400", platLabel));
        parts.push('<circle cx="' + (n.x + 10) + '" cy="' + (n.y + 62) + '" r="2.5" fill="' + kind.color + '"/>');
        parts.push(paint(n.x + 18, n.y + 66, "start", kindFill, 10, "400", kindLabel));
      } else {
        parts.push(paint(n.x + 12, n.y + 36, "start", titleFill, titleSize, "500", n.label));
        parts.push(paint(n.x + 12, n.y + 54, "start", platFill, 11, "400", platLabel));
        parts.push('<circle cx="' + (n.x + 15) + '" cy="' + (n.y + 68) + '" r="2.7" fill="' + kind.color + '"/>');
        parts.push(paint(n.x + 24, n.y + 72, "start", kindFill, 10.5, "400", kindLabel));
      }
      parts.push('</g>');
    });

    var any = CATALOG.some(function (n) { return model.nodes[n.id].value != null && model.nodes[n.id].value !== ""; });
    parts.push('<g pointer-events="none">');
    parts.push(paint(24, 24, "start", INK, 16, "500", "Goad"));
    parts.push(paint(78, 24, "start", "#9aa8bc", 13, "400", "Application topology"));
    parts.push('<circle cx="236" cy="19" r="3.5" fill="' + (any ? HEALTH.up : HEALTH.unknown) + '"><animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/></circle>');
    parts.push(paint(246, 24, "start", "#9aa8bc", 12, "400", any ? "Live" : "Waiting"));
    var lx = 310;
    [["HTTP", PROTO.HTTP], ["HTTPS", PROTO.HTTPS], ["TCP", PROTO.TCP], ["MCP", PROTO.MCP], ["OAuth", PROTO.OAuth]].forEach(function (item) {
      parts.push('<line x1="' + lx + '" y1="20" x2="' + (lx + 16) + '" y2="20" stroke="' + item[1] + '" stroke-width="1.2" opacity="0.8"/>');
      parts.push(paint(lx + 20, 24, "start", "#9aa8bc", 11, "400", item[0]));
      lx += item[0].length * 6.4 + 36;
    });

    var hy = 48;
    var hx = 24;
    ["vks", "tanzu", "vm", "dsm", "private-ai", "avi", "agentminder", "vcf"].forEach(function (key) {
      var plat = PLATFORMS[key];
      parts.push('<rect x="' + hx + '" y="' + (hy - 9) + '" width="10" height="10" rx="2" fill="' + plat.accent + '"/>');
      parts.push(paint(hx + 14, hy, "start", "#d5deea", 11, "400", plat.legend));
      hx += 14 + plat.legend.length * 6.3 + 14;
    });
    hx += 8;
    ["app", "agent", "mcp", "data", "model", "platform"].forEach(function (key) {
      var kind = KINDS[key];
      parts.push('<circle cx="' + (hx + 3) + '" cy="' + (hy - 4) + '" r="3" fill="' + kind.color + '"/>');
      parts.push(paint(hx + 10, hy, "start", "#b7c3d4", 11, "400", kind.legend));
      hx += 10 + kind.legend.length * 6.2 + 12;
    });
    hx += 6;
    parts.push('<circle cx="' + (hx + 4) + '" cy="' + (hy - 4) + '" r="4" fill="' + HEALTH.up + '"/>');
    parts.push(paint(hx + 12, hy, "start", "#d5deea", 11, "400", "up"));
    parts.push('<circle cx="' + (hx + 42) + '" cy="' + (hy - 4) + '" r="4" fill="' + HEALTH.down + '"/>');
    parts.push(paint(hx + 50, hy, "start", "#d5deea", 11, "400", "down"));
    parts.push('</g>');
    parts.push('</svg>');
    return parts.join("");
  }

  function tipRow(label, value) {
    if (blank(value)) return null;
    return React.createElement("div", {
      style: { display: "flex", justifyContent: "space-between", gap: 16, padding: "3px 0", fontSize: 12 }
    },
      React.createElement("span", { style: { color: "#8ea0b8", flex: "0 0 auto" } }, label),
      React.createElement("span", { style: { color: "#e8eef8", textAlign: "right", wordBreak: "break-all" } }, value)
    );
  }

  function tooltip(tip, model, width, height) {
    var kind = tip.key.slice(0, 1);
    var id = tip.key.slice(2);
    var body;
    var title;
    var accent = "#79b8ff";
    if (kind === "n") {
      var n = model.nodes[id];
      if (!n) return null;
      title = n.title || n.label;
      accent = HEALTH[n.state];
      var health = n.state === "up" ? "Up" : n.state === "down" ? "Down" : n.state === "slow" ? "Slow" : "Unknown";
      var lat = n.latency != null && !isNaN(n.latency) ? Math.round(n.latency) + " ms" : "";
      var platName = (PLATFORMS[n.platform] && PLATFORMS[n.platform].legend) || n.platform;
      var kindName = (KINDS[n.kind] && KINDS[n.kind].legend) || n.kind;
      body = [
        tipRow("Health", health),
        tipRow("Platform", platName),
        tipRow("Workload", kindName),
        tipRow("Cluster", n.cluster),
        tipRow("Namespace", n.namespace),
        tipRow("Node", n.node),
        tipRow("IP", n.ip),
        tipRow("Endpoint", n.endpoint),
        tipRow("Version", n.version),
        tipRow("Latency", lat)
      ];
    } else {
      var e = model.edges[id];
      if (!e) return null;
      accent = e.state === "down" ? HEALTH.down : protoColor(e.protocol);
      var src = model.nodes[e.source];
      var dst = model.nodes[e.target];
      function latOf(node) {
        if (!node || node.latency == null || isNaN(node.latency)) return "—";
        return Math.round(node.latency) + " ms";
      }
      title = (src ? src.label : e.source) + "  →  " + (dst ? dst.label : e.target);
      body = [
        tipRow("Protocol", e.protocol),
        tipRow("State", e.state === "up" ? "Open" : e.state === "down" ? "Down" : "Unknown"),
        tipRow("From", src ? src.label : e.source),
        tipRow("To", dst ? dst.label : e.target),
        tipRow("From latency", latOf(src)),
        tipRow("To latency", latOf(dst))
      ];
    }
    var left = tip.x;
    var top = tip.y;
    if (left > width - 320) left = Math.max(8, tip.x - 310);
    if (top > height - 240) top = Math.max(8, tip.y - 220);
    return React.createElement("div", {
      style: {
        position: "absolute", left: left, top: top, width: 292, zIndex: 5,
        background: "rgba(10,14,24,0.96)", border: "1px solid rgba(255,255,255,0.12)",
        borderRadius: 14, padding: "12px 14px", pointerEvents: "none",
        boxShadow: "0 16px 48px rgba(0,0,0,0.45)", color: "#e8eef8"
      }
    },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: 8 } },
        React.createElement("span", { style: { width: 8, height: 8, borderRadius: 99, background: accent, display: "inline-block" } }),
        React.createElement("strong", { style: { fontSize: 14, fontWeight: 500 } }, title)
      ),
      body
    );
  }

  function TopologyPanel(props) {
    var model = compose(readSeries(props.data));
    var stamp = stampOf(model);
    var svg = React.useMemo(function () { return buildSvg(model); }, [stamp]);
    var tipState = React.useState(null);
    var tip = tipState[0];
    var setTip = tipState[1];
    function move(ev) {
      var node = ev.target && ev.target.closest ? ev.target.closest("[data-k]") : null;
      var key = node ? node.getAttribute("data-k") : "";
      if (!key) {
        setTip(function (prev) { return prev ? null : prev; });
        return;
      }
      var box = ev.currentTarget.getBoundingClientRect();
      var x = ev.clientX - box.left + 16;
      var y = ev.clientY - box.top + 16;
      setTip(function (prev) {
        if (prev && prev.key === key && Math.abs(prev.x - x) < 4 && Math.abs(prev.y - y) < 4) return prev;
        return { key: key, x: x, y: y };
      });
    }
    return React.createElement("div", {
      onMouseMove: move,
      onMouseLeave: function () { setTip(null); },
      style: {
        width: props.width, height: props.height, position: "relative",
        background: "#070b14", overflow: "hidden"
      }
    },
      React.createElement("div", { style: { width: "100%", height: "100%" }, dangerouslySetInnerHTML: { __html: svg } }),
      tip ? tooltip(tip, model, props.width || 1920, props.height || 1080) : null
    );
  }

  var Plugin = gd.PanelPlugin;
  var plugin = new Plugin(TopologyPanel);
  if (plugin.setNoPadding) plugin = plugin.setNoPadding();
  var api = { plugin: plugin, build: buildSvg, demo: demo, read: readSeries, compose: compose, placed: PLACED, routes: ROUTES, edges: EDGES };
  if (typeof window !== "undefined") window.GoadTopo = api;
  return api;
});
