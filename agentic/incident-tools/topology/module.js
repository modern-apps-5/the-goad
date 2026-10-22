define(["react", "@grafana/data"], function (ReactMod, dataMod) {
  "use strict";

  var React = ReactMod && ReactMod.useState ? ReactMod : (ReactMod && ReactMod.default) || ReactMod;
  var gd = dataMod && dataMod.PanelPlugin ? dataMod : (dataMod && dataMod.default) || dataMod;

  var HEALTH = { up: "#3dd68c", down: "#ff5d73", slow: "#f5c16c", unknown: "#64748b" };
  var PROTO = { HTTP: "#79b8ff", HTTPS: "#d2a8ff", TCP: "#e3b341", MCP: "#56d4a0", OAuth: "#f0883e" };

  // Top to bottom: applications, Tanzu supply chain (only under the
  // Cloud Foundry apps), VKS, VCF. Gutters are the only legal wire paths.
  var G = {
    tzX: 24, tzW: 400, tzR: 424,
    appX: 520, appW: 860, appR: 1380,
    paiX: 1432, paiW: 400, paiR: 1832,
    vksX: 24, vksW: 1124,
    amX: 1164, amW: 660,
    vcfX: 24, vcfW: 1200,
    dsmX: 1240, dsmW: 584,
    top: 120,
    aY: 164, aH: 96,
    bY: 344, bH: 96,
    tzBot: 524,
    platY: 540, platH: 92,
    r1: 172, rowH: 56,
    r2: 312,
    r3: 424,
    r4: 508,
    appBot: 632,
    vksY: 648, vksH: 172,
    vcfY: 836, vcfH: 212,
    yK8s: 270, yVcf: 280, yCfQ: 290, yCfZ: 300,
    yLbQ: 310, yLbO: 320, yLbA: 330,
    yUsers: 304,
    yKq: 452, yKo: 464, yKm: 476,
    yVq: 488, yVo: 500, yVm: 512,
    yZi: 448, yZc: 460,
    yCart: 236, yOrder: 246, yMusU: 256, yChO: 266, yOrchM: 276,
    yMd: 286, yCd: 296,
    yShopO: 376, yTr: 384, yShopD: 392, yOrchQ: 400, yMusD: 408, yChatD: 416,
    yZr: 488, yZcache: 496,
    yBk: 576, yBv: 590,
    lane: 160,
    sky: [58, 66, 74, 82, 90, 98, 106],
    col: [432, 440, 448, 456, 464, 472, 480, 488, 496, 504, 512],
    paiC: [1388, 1396, 1404, 1412],
    tray: [1844, 1852, 1860, 1868, 1876, 1884, 1892, 1900, 1908],
    leftU: 8, leftZ: 16
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
    meta("users-vm", "Users VM", "VM Service", "vm", "wide", "music-store", "music-store-8q8l6", "music-users", "10.47.7.52", "http://10.47.7.52:5003/health", "ubuntu-24.04-cloud"),
    meta("am-api", "API", "Cluster", "cluster", "stack", "agentminder", "agentminder-z7v8k", "—", "10.47.7.77", "10.47.7.77:6443", KUBE),
    meta("am-cp", "Control", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-5nprd-9btlg", "172.30.0.34", "172.30.0.34:10250", KUBE),
    meta("am-w-7dsds", "7dsds", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-7dsds", "172.30.0.36", "172.30.0.36:10250", KUBE),
    meta("am-w-gpn6h", "gpn6h", "Node", "server", "stack", "agentminder", "agentminder-z7v8k", "agentminder-workers-h746j-6mwj7-gpn6h", "172.30.0.35", "172.30.0.35:10250", KUBE),
    meta("am-ui", "Console", "AgentMinder", "window", "stack", "agentminder", "ssp", "—", "10.47.7.82", "https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/", "console"),
    meta("music", "Music shop", "store", "shop", "wide", "music-store", "metal-music-store", N8, "10.96.203.228", "http://music-store-1-service.metal-music-store.svc:5000/", "python:3.12-slim"),
    meta("chat", "Chat", "assistant", "chat", "wide", "music-store", "metal-music-store", N8, "10.103.127.222", "http://chat-service.metal-music-store.svc:5005/health", "python:3.12-slim"),
    meta("cart", "Cart", "store", "cart", "wide", "music-store", "metal-music-store", N8, "10.110.165.207", "http://cart-service.metal-music-store.svc:5002/health", "python:3.12-slim"),
    meta("order", "Order", "store", "order", "wide", "music-store", "metal-music-store", N8, "10.101.157.182", "http://order-service.metal-music-store.svc:5001/health", "python:3.12-slim"),
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
    meta("vcf-mcp", "VCF", "MCP server", "plug", "wide", "music-store", "metal-music-app-agentic-system", NG, "10.47.7.86", "http://vcf-mcp.goad.gpu.set.lab/mcp", "python:3.12-slim")
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
  CATALOG.forEach(function (n) { BY_ID[n.id] = n; });

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

  function layout() {
    var nodes = {};
    var tzCard = 116;
    var tzGap = 10;
    var tzTotal = 3 * tzCard + 2 * tzGap;
    var tz0 = G.tzX + Math.round((G.tzW - tzTotal) / 2);
    var step = tzCard + tzGap;
    row(nodes, ["incident", "cf-orch", "lb-agent"], tz0, G.aY, tzCard, G.aH, tzGap, { mode: "stack" });
    place(nodes, "k8s-agent", tz0, G.bY, tzCard, G.bH, { mode: "stack" });
    place(nodes, "vcf-agent", tz0 + 2 * step, G.bY, tzCard, G.bH, { mode: "stack" });

    var aw = 132;
    var ag = 8;
    var a0 = G.appX + 16;
    row(nodes, ["users-vm", "music", "chat", "cart", "order"], a0, G.r1, aw, G.rowH, ag);
    row(nodes, ["zammad", "zammad-db", "zammad-redis", "zammad-cache", "pii", "orch"], a0, G.r2, aw, G.rowH, ag);
    row(nodes, ["avi-mcp", "k8s-mcp", "vcf-mcp"], a0, G.r3, aw, G.rowH, ag);

    place(nodes, "qwen", G.paiX + 24, 168, 200, 170);
    place(nodes, "clm", G.paiX + 24, 428, 200, 168);

    row(nodes, ["vks-api", "cp-pwtc2", "worker-8n8n5", "worker-gjwhn"], G.appX + 24, 648, 190, 84, 12);
    var amW = 70;
    var amGap = 6;
    var am0 = G.paiX + 16;
    row(nodes, ["am-api", "am-cp", "am-w-7dsds", "am-w-gpn6h", "am-ui"], am0, 658, amW, 92, amGap);

    place(nodes, "dsm", 1416, G.vcfY + 90, 280, 96, { mode: "wide" });

    var zones = [
      { id: "cfapps", title: "Applications", x: G.tzX, y: G.top, w: G.tzW, h: G.tzBot - G.top, accent: "#79b8ff" },
      { id: "tanzu", title: "Tanzu Platform", mark: "tanzu", note: "Supply chain", watermark: true, x: G.tzX, y: G.platY, w: G.tzW, h: G.platH, accent: "#79b8ff" },
      { id: "vks", title: "VKS  ·  music-store", mark: "vks", x: G.appX, y: G.top, w: G.appW, h: 760 - G.top, accent: "#56d4a0" },
      { id: "pai", title: "Private AI", mark: "pai", x: G.paiX, y: G.top, w: G.paiW, h: 480, accent: "#d2a8ff" },
      { id: "am", title: "AgentMinder", mark: "agentminder", x: G.paiX, y: 616, w: G.paiW, h: 144, accent: "#f0883e" },
      { id: "vcf", title: "VCF  ·  vSphere Supervisor", mark: "vcf", x: 24, y: G.vcfY, w: 1800, h: G.vcfH, accent: "#79b8ff" },
      { id: "dsmz", title: "DSM", mark: "dsm", x: 1288, y: G.vcfY + 40, w: 500, h: G.vcfH - 56, accent: "#e3b341" }
    ];
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
    var col = G.col;
    var tray = G.tray;
    var pai = G.paiC;
    var sky = G.sky;
    var q = N.qwen;
    var dsm = N.dsm;
    var ui = N["am-ui"];

    function skyTo(id, node, leaveY, colX, skyY, trayX, enterY, side) {
      add(id, [
        [cx(node), B(node)],
        [cx(node), leaveY],
        [colX, leaveY],
        [colX, skyY],
        [trayX, skyY],
        [trayX, enterY],
        [side, enterY]
      ]);
    }

    add("e-music-vm", hlink(N["users-vm"], N.music));
    add("e-music-chat", hlink(N.music, N.chat));
    add("e-music-cart", rail(N.music, N.cart, G.yCart, "s", "s"));
    add("e-music-order", rail(N.music, N.order, G.yOrder, "s", "s"));
    add("e-chat-order", rail(N.chat, N.order, G.yChO, "s", "s"));
    add("e-orch-music", rail(N.orch, N.music, G.yOrchM, "n", "s"));
    add("e-zammad-db", hlink(N.zammad, N["zammad-db"]));
    add("e-zammad-redis", rail(N.zammad, N["zammad-redis"], 384, "s", "s"));
    add("e-zammad-cache", rail(N.zammad, N["zammad-cache"], 396, "s", "s"));
    add("e-incident-orch", hlink(N.incident, N["cf-orch"]));
    add("e-cforch-lb", hlink(N["cf-orch"], N["lb-agent"]));
    add("e-cforch-k8s", rail(N["cf-orch"], N["k8s-agent"], G.yK8s, "s", "n"));
    add("e-cforch-vcf", rail(N["cf-orch"], N["vcf-agent"], G.yVcf, "s", "n"));

    add("e-incident-zammad", [
      [L(N.incident), cy(N.incident)],
      [G.leftZ, cy(N.incident)],
      [G.leftZ, 328],
      [L(N.zammad), 328]
    ]);
    add("e-cforch-zammad", [
      [cx(N["cf-orch"]), B(N["cf-orch"])],
      [cx(N["cf-orch"]), G.yCfZ],
      [col[10], G.yCfZ],
      [col[10], 340],
      [L(N.zammad), 340]
    ]);

    add("e-chat-qwen", [
      [cx(N.chat), T(N.chat)],
      [cx(N.chat), G.lane],
      [pai[0], G.lane],
      [pai[0], cy(q)],
      [L(q), cy(q)]
    ]);
    add("e-orch-qwen", [
      [cx(N.orch), B(N.orch)],
      [cx(N.orch), G.yOrchQ],
      [cx(q), G.yOrchQ],
      [cx(q), B(q)]
    ]);
    skyTo("e-cforch-qwen", N["cf-orch"], G.yCfQ, col[0], sky[0], tray[0], cy(q) - 24, Rt(q));
    skyTo("e-lb-qwen", N["lb-agent"], G.yLbQ, col[1], sky[1], tray[1], cy(q) - 8, Rt(q));
    skyTo("e-k8s-qwen", N["k8s-agent"], G.yKq, col[2], sky[2], tray[2], cy(q) + 8, Rt(q));
    skyTo("e-vcf-qwen", N["vcf-agent"], G.yVq, col[3], sky[3], tray[3], cy(q) + 24, Rt(q));

    skyTo("e-lb-am", N["lb-agent"], G.yLbO, col[4], sky[4], tray[4], cy(ui) - 16, Rt(ui));
    skyTo("e-k8s-am", N["k8s-agent"], G.yKo, col[5], sky[5], tray[5], cy(ui), Rt(ui));
    skyTo("e-vcf-am", N["vcf-agent"], G.yVo, col[6], sky[6], tray[6], cy(ui) + 16, Rt(ui));

    add("e-lb-avi", [
      [cx(N["lb-agent"]), B(N["lb-agent"])],
      [cx(N["lb-agent"]), G.yLbA],
      [col[7], G.yLbA],
      [col[7], cy(N["avi-mcp"])],
      [L(N["avi-mcp"]), cy(N["avi-mcp"])]
    ]);
    add("e-k8s-mcp", [
      [cx(N["k8s-agent"]), B(N["k8s-agent"])],
      [cx(N["k8s-agent"]), G.yKm],
      [col[8], G.yKm],
      [col[8], G.yBk],
      [cx(N["k8s-mcp"]), G.yBk],
      [cx(N["k8s-mcp"]), B(N["k8s-mcp"])]
    ]);
    add("e-vcf-mcp", [
      [cx(N["vcf-agent"]), B(N["vcf-agent"])],
      [cx(N["vcf-agent"]), G.yVm],
      [col[9], G.yVm],
      [col[9], G.yBv],
      [cx(N["vcf-mcp"]), G.yBv],
      [cx(N["vcf-mcp"]), B(N["vcf-mcp"])]
    ]);

    function dsmVia(id, node, leaveY, paiX, slotY, trayX, dy) {
      add(id, [
        [cx(node), B(node)],
        [cx(node), leaveY],
        [paiX, leaveY],
        [paiX, slotY],
        [trayX, slotY],
        [trayX, cy(dsm) + dy],
        [Rt(dsm), cy(dsm) + dy]
      ]);
    }
    dsmVia("e-music-dsm", N.music, G.yMd, pai[1], G.yMusD, tray[7], -18);
    dsmVia("e-chat-dsm", N.chat, G.yCd, pai[2], G.yChatD, tray[8], 0);
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
      pai: '<rect x="5.2" y="5.2" width="7.6" height="7.6" rx="1.5"' + s + '/><path d="M7.4 2v2.4M10.6 2v2.4M7.4 13.6V16M10.6 13.6V16M2 7.4h2.4M2 10.6h2.4M13.6 7.4H16M13.6 10.6H16"' + s + '/>'
    };
    return paths[name] || "";
  }

  function icon(name) {
    var s = ' fill="none" stroke="#d7e2f0" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"';
    var f = ' fill="#d7e2f0" stroke="none"';
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
    parts.push('<linearGradient id="zoneFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#172338"/><stop offset="1" stop-color="#0c121c"/></linearGradient>');
    parts.push('<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity="0.07"/><stop offset="0.45" stop-color="#ffffff" stop-opacity="0"/></linearGradient>');
    parts.push('<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="rgba(255,255,255,0.035)"/></pattern>');
    parts.push('<filter id="blur" x="-70%" y="-70%" width="240%" height="240%"><feGaussianBlur stdDeviation="8"/></filter>');
    parts.push('<marker id="chev" viewBox="0 0 8 8" refX="6.2" refY="4" markerWidth="5" markerHeight="5" orient="auto"><path d="M1.4 1.5 L6.2 4 L1.4 6.5" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker>');
    parts.push('<style>text{font-family:Inter,Segoe UI,system-ui,sans-serif}</style>');
    parts.push('</defs>');
    parts.push('<rect width="1920" height="1080" fill="#070b14"/>');
    parts.push('<ellipse cx="260" cy="-20" rx="760" ry="340" fill="#16325c" opacity="0.45"/>');
    parts.push('<ellipse cx="1680" cy="1120" rx="680" ry="320" fill="#2a1848" opacity="0.4"/>');
    parts.push('<rect width="1920" height="1080" fill="url(#dots)"/>');

    PLACED.zones.forEach(function (z) {
      parts.push('<rect x="' + z.x + '" y="' + z.y + '" width="' + z.w + '" height="' + z.h + '" rx="22" fill="url(#zoneFill)" stroke="' + z.accent + '" stroke-opacity="0.38" stroke-width="1.25"/>');
      var tx = z.x + 18;
      if (z.mark) {
        parts.push('<g transform="translate(' + (z.x + 16) + ' ' + (z.y + 12) + ')">' + badge(z.mark, z.accent) + '</g>');
        tx = z.x + 40;
      }
      parts.push('<text x="' + tx + '" y="' + (z.y + 26) + '" fill="' + z.accent + '" font-size="13" font-weight="650" letter-spacing="1.4">' + esc(z.title) + '</text>');
      if (z.suffix) {
        var sx = tx + Math.round(z.title.length * 8.4);
        parts.push('<text x="' + sx + '" y="' + (z.y + 26) + '" fill="#8ea0b8" font-size="11" font-weight="550" letter-spacing="1">' + esc(z.suffix) + '</text>');
      }
      parts.push('<rect x="' + tx + '" y="' + (z.y + 34) + '" width="32" height="2" rx="1" fill="' + z.accent + '" opacity="0.8"/>');
      if (z.watermark && z.mark) {
        parts.push('<g transform="translate(' + (z.x + z.w - 86) + ' ' + (z.y + 22) + ') scale(3)" opacity="0.28">' + badge(z.mark, z.accent) + '</g>');
      }
      if (z.note) {
        parts.push('<text x="' + (z.x + z.w * 0.42) + '" y="' + (z.y + z.h * 0.62) + '" text-anchor="middle" fill="#b7c6da" font-size="15" font-weight="550">' + esc(z.note) + '</text>');
      }
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
      var color = down ? "#ff5d73" : (unknown ? "#5c6b82" : item.color);
      var width = down ? 2.3 : (item.len > 280 ? 1.8 : 1.55);
      var dash = down ? ' stroke-dasharray="7 6"' : (unknown ? ' stroke-dasharray="2 5"' : "");
      var marker = item.len > 48 && !unknown ? ' marker-end="url(#chev)"' : "";
      parts.push('<path id="p-' + item.id + '" d="' + d + '" fill="none" stroke="' + color + '" stroke-width="' + width + '" stroke-linecap="round" stroke-linejoin="round" opacity="' + (down ? "0.95" : "0.82") + '"' + dash + marker + '/>');
      parts.push('<path data-k="e:' + item.id + '" d="' + d + '" fill="none" stroke="transparent" stroke-width="14" style="cursor:pointer"/>');
      if (!down && !unknown) {
        var dur = Math.max(2.6, Math.min(7.5, item.len / 150)).toFixed(1);
        var begin = ((index % 7) * 0.35).toFixed(2);
        parts.push('<circle r="3" fill="' + color + '"><animateMotion dur="' + dur + 's" begin="' + begin + 's" repeatCount="indefinite" rotate="auto"><mpath href="#p-' + item.id + '" xlink:href="#p-' + item.id + '"/></animateMotion></circle>');
      }
    });

    CATALOG.forEach(function (spec) {
      var n = PLACED.nodes[spec.id];
      var info = model.nodes[spec.id];
      var color = HEALTH[info.state] || HEALTH.unknown;
      var glow = info.state === "unknown" ? 0 : (info.state === "down" ? 0.5 : 0.3);
      if (glow) {
        parts.push('<rect x="' + (n.x - 4) + '" y="' + (n.y - 4) + '" width="' + (n.w + 8) + '" height="' + (n.h + 8) + '" rx="18" fill="' + color + '" opacity="' + glow + '" filter="url(#blur)"/>');
      }
      parts.push('<g data-k="n:' + spec.id + '" style="cursor:pointer">');
      parts.push('<rect x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="14" fill="#121a2b" stroke="' + color + '" stroke-width="1.6"/>');
      parts.push('<rect x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="14" fill="url(#sheen)"/>');
      if (n.mode !== "feature") {
        parts.push('<rect x="' + (n.x + 1.5) + '" y="' + (n.y + 12) + '" width="3" height="' + (n.h - 24) + '" rx="1.5" fill="' + color + '"/>');
      }
      var size = n.mode === "feature" ? 42 : (n.mode === "stack" ? 28 : 24);
      var ix, iy;
      if (n.mode === "feature") {
        ix = n.x + (n.w - size) / 2;
        iy = n.y + 36;
      } else if (n.mode === "stack") {
        ix = n.x + (n.w - size) / 2;
        iy = n.y + 16;
      } else {
        ix = n.x + 14;
        iy = n.y + (n.h - size) / 2;
      }
      parts.push('<g transform="translate(' + ix.toFixed(1) + ' ' + iy.toFixed(1) + ') scale(' + (size / 24).toFixed(3) + ')">' + icon(n.icon) + '</g>');
      if (n.mode === "feature") {
        parts.push('<text x="' + mx(n) + '" y="' + (n.y + 128) + '" text-anchor="middle" fill="#f4f7fb" font-size="18" font-weight="650">' + esc(n.label) + '</text>');
        parts.push('<text x="' + mx(n) + '" y="' + (n.y + 152) + '" text-anchor="middle" fill="#93a4bb" font-size="12">' + esc(n.role) + '</text>');
      } else if (n.mode === "stack") {
        parts.push('<text x="' + mx(n) + '" y="' + (n.y + 62) + '" text-anchor="middle" fill="#f4f7fb" font-size="13" font-weight="650">' + esc(n.label) + '</text>');
        parts.push('<text x="' + mx(n) + '" y="' + (n.y + 80) + '" text-anchor="middle" fill="#93a4bb" font-size="11">' + esc(n.role) + '</text>');
      } else {
        var tx = n.x + 46;
        parts.push('<text x="' + tx + '" y="' + (n.y + n.h / 2 - 2) + '" fill="#f4f7fb" font-size="13" font-weight="650">' + esc(n.label) + '</text>');
        parts.push('<text x="' + tx + '" y="' + (n.y + n.h / 2 + 14) + '" fill="#93a4bb" font-size="11">' + esc(n.role) + '</text>');
      }
      parts.push('<circle cx="' + (n.x + n.w - 12) + '" cy="' + (n.y + 12) + '" r="4" fill="' + color + '" stroke="#121a2b" stroke-width="2"/>');
      parts.push('</g>');
    });

    var any = CATALOG.some(function (n) { return model.nodes[n.id].value != null && model.nodes[n.id].value !== ""; });
    parts.push('<g pointer-events="none">');
    parts.push('<rect x="28" y="16" width="34" height="34" rx="9" fill="#e23b4a"/>');
    parts.push('<path d="M36 40 L45 22 L54 40" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>');
    parts.push('<text x="74" y="40" fill="#f4f7fb" font-size="22" font-weight="700">Goad</text>');
    parts.push('<text x="148" y="40" fill="#8ea0b8" font-size="15">Application topology</text>');
    parts.push('<circle cx="330" cy="35" r="4" fill="' + (any ? "#3dd68c" : "#64748b") + '"><animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/></circle>');
    parts.push('<text x="340" y="40" fill="#8ea0b8" font-size="12">' + (any ? "Live" : "Waiting") + '</text>');
    var legend = [["HTTP", PROTO.HTTP], ["HTTPS", PROTO.HTTPS], ["TCP", PROTO.TCP], ["MCP", PROTO.MCP], ["OAuth", PROTO.OAuth]];
    var lx = 1120;
    legend.forEach(function (item) {
      parts.push('<line x1="' + lx + '" y1="35" x2="' + (lx + 22) + '" y2="35" stroke="' + item[1] + '" stroke-width="2"/>');
      parts.push('<circle cx="' + (lx + 11) + '" cy="35" r="2.4" fill="' + item[1] + '"/>');
      parts.push('<text x="' + (lx + 28) + '" y="39" fill="#c5d0e0" font-size="12">' + item[0] + '</text>');
      lx += 92;
    });
    parts.push('<line x1="' + lx + '" y1="35" x2="' + (lx + 22) + '" y2="35" stroke="#ff5d73" stroke-width="2" stroke-dasharray="4 3"/>');
    parts.push('<text x="' + (lx + 28) + '" y="39" fill="#c5d0e0" font-size="12">Down</text>');
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
      body = [
        tipRow("Health", health),
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
        React.createElement("strong", { style: { fontSize: 14, fontWeight: 650 } }, title)
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
