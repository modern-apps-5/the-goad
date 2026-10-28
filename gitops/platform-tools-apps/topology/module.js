define(["react", "@grafana/data"], function (ReactMod, dataMod) {
  "use strict";

  var React = ReactMod && ReactMod.useState ? ReactMod : (ReactMod && ReactMod.default) || ReactMod;
  var gd = dataMod && dataMod.PanelPlugin ? dataMod : (dataMod && dataMod.default) || dataMod;

  var HEALTH = { up: "#3dd68c", down: "#ff5d73", slow: "#f5c16c", unknown: "#64748b" };
  var PROTO = { HTTP: "#79b8ff", HTTPS: "#d2a8ff", TCP: "#e3b341", MCP: "#7ec8c3", OAuth: "#f0a35e" };
  var INK = "#e8eef6";
  var BG = "#070b14";

  // Color is only the platform a workload runs on. Group outline, header
  // band, and the thin box stroke share that accent. Boxes stay the panel
  // color. Green and red stay on the status dot. AgentMinder is a second
  // VKS cluster, so it uses the VKS accent and keeps its name in the header.
  var PLATFORMS = {
    vks: { legend: "VKS", header: "VKS · music-store", box: "VKS", accent: "#4c8dff", ink: "#b9d4ff" },
    tanzu: { legend: "Tanzu", header: "Tanzu Platform", box: "Tanzu", accent: "#b794f6", ink: "#e0d4ff" },
    vm: { legend: "VM", header: "VM Service", box: "VM", accent: "#f5a524", ink: "#ffd7a1" },
    dsm: { legend: "DSM", header: "DSM", box: "DSM", accent: "#e6c229", ink: "#ffe58a" },
    "private-ai": { legend: "Private AI", header: "Private AI", box: "Private AI", accent: "#e879f9", ink: "#f6c2ff" },
    vcf: { legend: "VCF", header: "VCF", box: "VCF", accent: "#94a3b8", ink: "#d5dee8" }
  };
  var KINDS = {
    app: { legend: "app", color: "#8eb4ff" },
    agent: { legend: "agent", color: "#d4b6ff" },
    mcp: { legend: "MCP", color: "#7fd6ea" },
    data: { legend: "data", color: "#f0d060" },
    model: { legend: "model", color: "#f0a0e8" },
    platform: { legend: "platform", color: "#c5d0dc" },
    vm: { legend: "VM", color: "#ffb15a" }
  };
  var PLATFORM_OF = {
    "vks-api": "vks", "music-nodes": "vks",
    "users-vm": "vm",
    "am-ui": "vks",
    music: "vks", chat: "vks", cart: "vks", order: "vks",
    zammad: "vks", "zammad-db": "vks", "zammad-redis": "vks", "zammad-cache": "vks",
    dsm: "dsm", qwen: "private-ai",
    incident: "tanzu", "cf-orch": "tanzu", "lb-agent": "tanzu", "k8s-agent": "tanzu", "vcf-agent": "tanzu",
    pii: "tanzu", "avi-mcp": "tanzu", "k8s-mcp": "tanzu", "vcf-mcp": "tanzu",
    "vcf-ops": "vcf", vcfa: "vcf", vcenter: "vcf", nsx: "vcf"
  };
  var KIND_OF = {
    "vks-api": "platform", "music-nodes": "platform",
    "users-vm": "vm",
    "am-ui": "platform",
    music: "app", chat: "app", cart: "app", order: "app", pii: "app", zammad: "app",
    "zammad-db": "data", "zammad-redis": "data", "zammad-cache": "data",
    "k8s-mcp": "mcp", "vcf-mcp": "mcp", "avi-mcp": "mcp",
    dsm: "data", qwen: "model",
    incident: "agent", "cf-orch": "agent", "lb-agent": "agent", "k8s-agent": "agent", "vcf-agent": "agent",
    "vcf-ops": "platform", vcfa: "platform", vcenter: "platform", nsx: "platform"
  };

  // Groups follow where the workload runs. The sky lanes are spaced so the
  // long wires do not pile up on the top edge.
  var GEO = {
    tz: { x: 16, y: 148, w: 600, h: 608 },
    vm: { x: 628, y: 148, w: 124, h: 608 },
    vks: { x: 764, y: 148, w: 520, h: 608 },
    tools: { x: 1296, y: 148, w: 300, h: 608 },
    dsm: { x: 1608, y: 148, w: 130, h: 608 },
    pai: { x: 1750, y: 148, w: 154, h: 320 },
    am: { x: 1750, y: 480, w: 154, h: 276 },
    vcf: { x: 16, y: 768, w: 1888, h: 296 }
  };
  var SKY = [52, 70, 88, 106, 124];

  function meta(id, label, role, icon, mode, cluster, namespace, node, ip, endpoint, version) {
    return {
      id: id, label: label, role: role, icon: icon, mode: mode,
      cluster: cluster, namespace: namespace, node: node, ip: ip,
      endpoint: endpoint, version: version
    };
  }

  // No addresses: the blackbox exporter checks names, and the boxes show
  // the name each check uses (decision 21).
  var KUBE = "v1.36.2+vmware.2";
  var SPACE = "metal-music-app-agentic-system";
  function cf(app) { return "https://" + app + ".apps.goad.gpu.set.lab/health"; }
  var CATALOG = [
    meta("vks-api", "VKS API", "Cluster", "cluster", "wide", "music-store", "default", "—", "—", "kubernetes.default.svc:443", KUBE),
    meta("music-nodes", "Nodes", "Node", "server", "wide", "music-store", "—", "all nodes", "—", "kube_node_status_condition Ready", KUBE),
    meta("users-vm", "Users VM", "VM Service", "vm", "vmhost", "music-store", "music-store", "music-users", "—", "http://users-service.music-store.svc:5003/health", "ubuntu-24.04-cloud"),
    meta("am-ui", "Console", "AgentMinder", "window", "stack", "agentminder", "ssp", "—", "—", "https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/", "console"),
    meta("music", "Music shop", "store", "shop", "wide", "music-store", "music-store", "—", "—", "http://music-store-1-service.music-store.svc:5000/", "python:3.12-slim"),
    meta("chat", "Chat", "assistant", "chat", "wide", "music-store", "music-store", "—", "—", "http://chat-service.music-store.svc:5005/health", "python:3.12-slim"),
    meta("cart", "Cart", "store", "cart", "wide", "music-store", "music-store", "—", "—", "http://cart-service.music-store.svc:5002/health", "python:3.12-slim"),
    meta("order", "Order", "store", "order", "wide", "music-store", "music-store", "—", "—", "http://order-service.music-store.svc:5001/health", "python:3.12-slim"),
    meta("zammad", "Zammad", "Tickets", "ticket", "wide", "platform-tools", "incident-tools", "—", "—", "http://zammad-nginx.incident-tools.svc:8080/", "7.2.2"),
    meta("zammad-db", "Postgres", "Database", "db", "wide", "platform-tools", "incident-tools", "—", "—", "zammad-postgresql.incident-tools.svc:5432", "17.11"),
    meta("zammad-redis", "Redis", "Cache", "layers", "wide", "platform-tools", "incident-tools", "—", "—", "zammad-redis.incident-tools.svc:6379", "7.4"),
    meta("zammad-cache", "Memcached", "Cache", "box", "wide", "platform-tools", "incident-tools", "—", "—", "zammad-memcached.incident-tools.svc:11211", "1.6.45"),
    meta("dsm", "Catalog", "Postgres", "db", "feature", "music-store", "music-store", "—", "—", "postgres-service.music-store.svc:5432", "DSM PostgresCluster catalog"),
    meta("qwen", "Qwen", "qwen-14b-xlarge", "chip", "feature", "private-ai", "private-ai", "—", "—", "Private AI Services /models", "qwen-14b-xlarge"),
    meta("incident", "Incident", "Agent", "bot", "wide", "tanzu-cf", SPACE, "—", "—", cf("incident-response-agent"), "tanzu-agent"),
    meta("cf-orch", "Orchestrator", "Agent", "nodes", "wide", "tanzu-cf", SPACE, "—", "—", cf("metal-incident-live"), "harness.py"),
    meta("lb-agent", "Load balancer", "Agent", "bot", "wide", "tanzu-cf", SPACE, "—", "—", cf("lb-diagnostic-agent"), "tanzu-agent"),
    meta("k8s-agent", "Kubernetes", "Agent", "bot", "wide", "tanzu-cf", SPACE, "—", "—", cf("k8s-diagnostic-agent"), "tanzu-agent"),
    meta("vcf-agent", "VCF", "Agent", "bot", "wide", "tanzu-cf", SPACE, "—", "—", cf("vcf-diagnostic-agent"), "tanzu-agent"),
    meta("pii", "PII scrub", "filter", "shield", "wide", "tanzu-cf", SPACE, "—", "—", cf("pii-scrub"), "python"),
    meta("avi-mcp", "Avi", "MCP server", "plug", "wide", "tanzu-cf", SPACE, "—", "—", cf("metal-avi-mcp"), "python"),
    meta("k8s-mcp", "Kubernetes", "MCP server", "plug", "wide", "tanzu-cf", SPACE, "—", "—", cf("metal-k8s-mcp"), "python"),
    meta("vcf-mcp", "VCF", "MCP server", "plug", "wide", "tanzu-cf", SPACE, "—", "—", cf("metal-vcf-mcp"), "python"),
    meta("vcf-ops", "VCF Ops", "ops01", "pulse", "wide", "vcf", "ops01", "—", "—", "ops01.gpu.set.lab:443", "ops01.gpu.set.lab"),
    meta("vcfa", "VCFA", "Automation", "window", "wide", "vcf", "auto", "—", "—", "auto.gpu.set.lab:443", "auto.gpu.set.lab"),
    meta("vcenter", "vCenter", "vc01", "server", "wide", "vcf", "vc01", "—", "—", "vc01.gpu.set.lab:443", "vc01.gpu.set.lab"),
    meta("nsx", "NSX", "nsx01", "layers", "wide", "vcf", "nsx01", "—", "—", "nsx01.gpu.set.lab:443", "nsx01.gpu.set.lab")
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
    ["e-cforch-pii", "cf-orch", "pii", "HTTP"],
    ["e-cforch-zammad", "cf-orch", "zammad", "HTTPS"],
    ["e-cforch-qwen", "cf-orch", "qwen", "HTTPS"],
    ["e-lb-avi", "lb-agent", "avi-mcp", "MCP"],
    ["e-k8s-mcp", "k8s-agent", "k8s-mcp", "MCP"],
    ["e-vcf-mcp", "vcf-agent", "vcf-mcp", "MCP"],
    ["e-k8smcp-api", "k8s-mcp", "vks-api", "HTTPS"],
    ["e-vcfmcp-vcenter", "vcf-mcp", "vcenter", "HTTPS"],
    ["e-lb-am", "lb-agent", "am-ui", "OAuth"],
    ["e-k8s-am", "k8s-agent", "am-ui", "OAuth"],
    ["e-vcf-am", "vcf-agent", "am-ui", "OAuth"],
    ["e-lb-qwen", "lb-agent", "qwen", "HTTPS"],
    ["e-k8s-qwen", "k8s-agent", "qwen", "HTTPS"],
    ["e-vcf-qwen", "vcf-agent", "qwen", "HTTPS"],
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

  function zoneOf(key, mark, title) {
    var g = GEO[key];
    var platKey = key === "pai" ? "private-ai" : key === "tz" ? "tanzu" : (key === "am" || key === "tools") ? "vks" : key;
    var plat = PLATFORMS[platKey];
    return {
      id: key, title: title || plat.header, mark: mark, accent: plat.accent, ink: plat.ink,
      x: g.x, y: g.y, w: g.w, h: g.h
    };
  }

  function layout() {
    var nodes = {};
    // Tanzu: the agents on the left, and on the right what each one calls,
    // on the same row so the wire is straight.
    ["incident", "cf-orch", "lb-agent", "k8s-agent", "vcf-agent"].forEach(function (id, i) {
      place(nodes, id, 32, 192 + i * 98, 272, 88);
    });
    ["pii", "avi-mcp", "k8s-mcp", "vcf-mcp"].forEach(function (id, i) {
      place(nodes, id, 340, 192 + (i + 1) * 98, 260, 88);
    });
    place(nodes, "users-vm", 640, 192, 100, 118);
    row(nodes, ["music", "chat"], 784, 192, 234, 96, 12);
    row(nodes, ["cart", "order"], 784, 302, 234, 96, 12);
    var infra = {
      x: 776, y: 512, w: 496, h: 188,
      title: "VKS cluster infrastructure",
      accent: PLATFORMS.vks.accent, ink: PLATFORMS.vks.ink
    };
    row(nodes, ["vks-api", "music-nodes"], 794, 546, 224, 140, 12);
    ["zammad", "zammad-db", "zammad-redis", "zammad-cache"].forEach(function (id, i) {
      place(nodes, id, 1312, 192 + i * 110, 244, 96);
    });
    place(nodes, "dsm", 1620, 192, 106, 176);
    place(nodes, "qwen", 1762, 192, 130, 118);
    place(nodes, "am-ui", 1762, 530, 130, 96);
    var fw = 430;
    var fg = 20;
    var f0 = 16 + Math.round((1888 - (4 * fw + 3 * fg)) / 2);
    row(nodes, ["vcf-ops", "vcfa", "vcenter", "nsx"], f0, 812, fw, 200, fg);

    var zones = [
      zoneOf("tz", "tanzu"),
      zoneOf("vm", "vm"),
      zoneOf("vks", "vks"),
      zoneOf("tools", "vks", "VKS · platform-tools"),
      zoneOf("dsm", "dsm"),
      zoneOf("pai", "pai"),
      zoneOf("am", "vks", "AgentMinder"),
      zoneOf("vcf", "vcf")
    ];
    return { zones: zones, nodes: nodes, infra: infra };
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

    // Inside Tanzu.
    add("e-incident-orch", [
      [cx(N.incident), B(N.incident)],
      [cx(N.incident), T(N["cf-orch"])]
    ]);
    add("e-cforch-lb", [
      [cx(N["cf-orch"]) - 28, B(N["cf-orch"])],
      [cx(N["cf-orch"]) - 28, T(N["lb-agent"])]
    ]);
    add("e-cforch-k8s", [
      [L(N["cf-orch"]), cy(N["cf-orch"])],
      [22, cy(N["cf-orch"])],
      [22, cy(N["k8s-agent"])],
      [L(N["k8s-agent"]), cy(N["k8s-agent"])]
    ]);
    add("e-cforch-vcf", [
      [L(N["cf-orch"]), cy(N["cf-orch"]) + 12],
      [28, cy(N["cf-orch"]) + 12],
      [28, cy(N["vcf-agent"])],
      [L(N["vcf-agent"]), cy(N["vcf-agent"])]
    ]);
    add("e-cforch-pii", hlink(N["cf-orch"], N.pii));
    add("e-lb-avi", hlink(N["lb-agent"], N["avi-mcp"]));
    add("e-k8s-mcp", hlink(N["k8s-agent"], N["k8s-mcp"]));
    add("e-vcf-mcp", hlink(N["vcf-agent"], N["vcf-mcp"]));

    // Inside the music store cluster.
    add("e-music-chat", hlink(N.music, N.chat));
    add("e-music-vm", [
      [Rt(N["users-vm"]), cy(N.music)],
      [L(N.music), cy(N.music)]
    ]);
    add("e-music-cart", [
      [cx(N.music) - 16, B(N.music)],
      [cx(N.music) - 16, T(N.cart)]
    ]);
    add("e-music-order", [
      [cx(N.music) + 16, B(N.music)],
      [cx(N.music) + 16, 297],
      [cx(N.order) - 18, 297],
      [cx(N.order) - 18, T(N.order)]
    ]);
    add("e-chat-order", [
      [cx(N.chat) + 16, B(N.chat)],
      [cx(N.chat) + 16, T(N.order)]
    ]);

    // Zammad's column: rails on its right edge.
    [["e-zammad-db", "zammad-db", 10], ["e-zammad-redis", "zammad-redis", 18], ["e-zammad-cache", "zammad-cache", 26]].forEach(function (e) {
      var x = Rt(N.zammad) + e[2];
      add(e[0], [
        [Rt(N.zammad), cy(N.zammad) + e[2] - 18],
        [x, cy(N.zammad) + e[2] - 18],
        [x, cy(N[e[1]])],
        [Rt(N[e[1]]), cy(N[e[1]])]
      ]);
    });

    // Long wires. Each leaves through the gap under the Tanzu rows or over
    // the top of the zones, on its own lane.
    var under = 760;
    add("e-incident-zammad", [
      [cx(N.incident), T(N.incident)],
      [cx(N.incident), SKY[4] + 8],
      [1300, SKY[4] + 8],
      [1300, cy(N.zammad) - 12],
      [L(N.zammad), cy(N.zammad) - 12]
    ]);
    add("e-cforch-zammad", [
      [Rt(N["cf-orch"]), cy(N["cf-orch"]) - 22],
      [320, cy(N["cf-orch"]) - 22],
      [320, 180],
      [1304, 180],
      [1304, cy(N.zammad) + 12],
      [L(N.zammad), cy(N.zammad) + 12]
    ]);
    add("e-music-dsm", [
      [cx(N.music) - 40, T(N.music)],
      [cx(N.music) - 40, 172],
      [1612, 172],
      [1612, cy(N.dsm) - 16],
      [L(N.dsm), cy(N.dsm) - 16]
    ]);
    add("e-chat-dsm", [
      [cx(N.chat), T(N.chat)],
      [cx(N.chat), 164],
      [1616, 164],
      [1616, cy(N.dsm) + 28],
      [L(N.dsm), cy(N.dsm) + 28]
    ]);
    add("e-chat-qwen", [
      [cx(N.chat) + 30, T(N.chat)],
      [cx(N.chat) + 30, SKY[4]],
      [1770, SKY[4]],
      [1770, T(N.qwen)]
    ]);
    function sky(id, node, lane, dropX) {
      add(id, [
        [cx(node) + 60, T(node)],
        [cx(node) + 60, lane],
        [dropX, lane],
        [dropX, T(N.qwen)]
      ]);
    }
    sky("e-cforch-qwen", N["cf-orch"], SKY[0], 1800);
    sky("e-lb-qwen", N["lb-agent"], SKY[1], 1824);
    sky("e-k8s-qwen", N["k8s-agent"], SKY[2], 1848);
    sky("e-vcf-qwen", N["vcf-agent"], SKY[3], 1872);
    [["e-lb-am", "lb-agent", 0], ["e-k8s-am", "k8s-agent", 8], ["e-vcf-am", "vcf-agent", 16]].forEach(function (e) {
      add(e[0], [
        [cx(N[e[1]]) - 60 + e[2], B(N[e[1]])],
        [cx(N[e[1]]) - 60 + e[2], under - 4 + e[2] / 2],
        [1756 + e[2] / 2, under - 4 + e[2] / 2],
        [1756 + e[2] / 2, cy(N["am-ui"]) + e[2] - 8],
        [L(N["am-ui"]), cy(N["am-ui"]) + e[2] - 8]
      ]);
    });
    add("e-k8smcp-api", [
      [Rt(N["k8s-mcp"]), cy(N["k8s-mcp"])],
      [758, cy(N["k8s-mcp"])],
      [758, cy(N["vks-api"])],
      [L(N["vks-api"]), cy(N["vks-api"])]
    ]);
    add("e-vcfmcp-vcenter", [
      [cx(N["vcf-mcp"]), B(N["vcf-mcp"])],
      [cx(N["vcf-mcp"]), under + 2],
      [cx(N.vcenter), under + 2],
      [cx(N.vcenter), T(N.vcenter)]
    ]);
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
      var down = n.id === "zammad-cache";
      nodes[n.id] = { value: down ? 0 : 1, title: n.label };
      lats[n.id] = { value: n.id === "qwen" ? 42 : 16 };
    });
    EDGES.forEach(function (e) {
      edges[e[0]] = { value: e[0] === "e-zammad-cache" ? 0 : 1, protocol: e[3], source: e[1], target: e[2] };
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
      var head = z.title.length > 22 ? 13 : 14;
      parts.push('<clipPath id="' + clip + '"><rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="' + z.h + '" rx="14"/></clipPath>');
      parts.push('<rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="' + z.h + '" rx="14" fill="' + BG + '" fill-opacity="0.25" stroke="' + z.accent + '" stroke-width="1.5"/>');
      parts.push('<g clip-path="url(#' + clip + ')"><rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="30" fill="' + z.accent + '" fill-opacity="0.20"/></g>');
      var tx = z.x + 12;
      if (z.mark) {
        parts.push('<g transform="translate(' + (z.x + 10) + ' ' + (z.y + 7) + ')">' + badge(z.mark, z.ink) + '</g>');
        tx = z.x + 32;
      }
      parts.push(paint(tx, z.y + 20, "start", z.ink, head, "500", z.title));
    });
    if (PLACED.infra) {
      var inf = PLACED.infra;
      parts.push('<rect x="' + inf.x + '" y="' + inf.y + '" width="' + inf.w + '" height="' + inf.h + '" rx="12" fill="none" stroke="' + inf.accent + '" stroke-width="1.25" stroke-dasharray="7 5" stroke-opacity="0.85"/>');
      parts.push(paint(inf.x + 14, inf.y + 22, "start", inf.ink, 13, "500", inf.title));
    }

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
      var kindFill = down ? "#9aa6b6" : "#e7eef8";
      var kindDot = down ? "#6e7d90" : kind.color;
      var titleSize = n.h < 80 ? 14 : (n.w >= 300 ? 16 : (n.w >= 140 ? 15 : 14));
      var kindSize = n.w < 130 ? 11 : 12;
      var titleY = n.y + Math.round(n.h * (n.h < 80 ? 0.40 : 0.42));
      var kindY = titleY + (kindSize >= 12 ? 22 : 18);
      var kindX = n.x + (n.w >= 300 ? 22 : 14);
      parts.push('<g data-k="n:' + spec.id + '" style="cursor:pointer">');
      parts.push('<rect x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="10" fill="' + BG + '" stroke="' + plat.accent + '" stroke-width="1.5" stroke-opacity="' + (down ? "0.4" : "1") + '"/>');
      var dot = n.w >= 200 ? 4.5 : 3.5;
      parts.push('<circle cx="' + (n.x + n.w - dot - 7) + '" cy="' + (n.y + dot + 7) + '" r="' + dot + '" fill="' + color + '"/>');
      parts.push(paint(kindX, titleY, "start", titleFill, titleSize, "500", n.label));
      var kr = kindSize >= 12 ? 4 : 3.5;
      parts.push('<circle cx="' + (kindX + kr) + '" cy="' + (kindY - 4) + '" r="' + kr + '" fill="' + kindDot + '"/>');
      parts.push(paint(kindX + kr * 2 + 6, kindY, "start", kindFill, kindSize, "500", kind.legend));
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

    var hy = 24;
    var hx = lx + 20;
    ["vks", "tanzu", "vm", "dsm", "private-ai", "vcf"].forEach(function (key) {
      var plat = PLATFORMS[key];
      parts.push('<rect x="' + hx + '" y="' + (hy - 9) + '" width="10" height="10" rx="2" fill="' + plat.accent + '"/>');
      parts.push(paint(hx + 14, hy, "start", "#d5deea", 11, "400", plat.legend));
      hx += 14 + plat.legend.length * 6.3 + 14;
    });
    hx += 8;
    ["app", "agent", "mcp", "data", "model", "platform", "vm"].forEach(function (key) {
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
      style: { display: "flex", justifyContent: "space-between", gap: 18, padding: "5px 0", fontSize: 15, lineHeight: "20px" }
    },
      React.createElement("span", { style: { color: "#c5d4e8", flex: "0 0 auto" } }, label),
      React.createElement("span", { style: { color: "#ffffff", textAlign: "right", wordBreak: "break-all", fontWeight: 500 } }, value)
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
      if (id.indexOf("am-") === 0) platName = "VKS · AgentMinder";
      var kindName = (KINDS[n.kind] && KINDS[n.kind].legend) || n.kind;
      body = [
        tipRow("Status", health),
        tipRow("Platform", platName),
        tipRow("Kind", kindName),
        tipRow("Latency", lat),
        tipRow("Cluster", n.cluster),
        tipRow("Namespace", n.namespace),
        tipRow("Node", n.node),
        tipRow("IP", n.ip),
        tipRow("Endpoint", n.endpoint),
        tipRow("Version", n.version)
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
    if (left > width - 440) left = Math.max(8, tip.x - 430);
    if (top > height - 420) top = Math.max(8, tip.y - 400);
    return React.createElement("div", {
      style: {
        position: "absolute", left: left, top: top, width: 420, zIndex: 5,
        background: "rgba(8,12,22,0.97)", border: "1px solid rgba(232,238,248,0.28)",
        borderRadius: 14, padding: "16px 18px", pointerEvents: "none",
        boxShadow: "0 18px 48px rgba(0,0,0,0.55)", color: "#ffffff"
      }
    },
      React.createElement("div", { style: { display: "flex", alignItems: "center", gap: 10, marginBottom: 10 } },
        React.createElement("span", { style: { width: 10, height: 10, borderRadius: 99, background: accent, display: "inline-block" } }),
        React.createElement("strong", { style: { fontSize: 16, fontWeight: 500, letterSpacing: "0.01em" } }, title)
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
