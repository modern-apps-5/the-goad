#!/usr/bin/env python3
"""Create the Goad AgentMinder clients and resource servers.

Reads first. Stops if any of the names already exist. Talks only to the
AgentMinder named by AGENTMINDER_HOST. Does not print secrets.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path

INTENT = "urn:iam:agent:intent:"
NAMES = (
    "py-goad-incident-response",
    "py-goad-lb",
    "py-goad-k8s",
    "py-goad-vcf",
    "goad-k8s-mcp",
    "goad-vcf-mcp",
    "goad-avi-mcp",
)
SERVERS = {
    "goad-k8s-mcp": [
        "k8s_list_deployments",
        "k8s_list_pods",
        "k8s_events",
        "k8s_pod_logs",
        "k8s_list_namespaces",
    ],
    "goad-avi-mcp": [
        "avi_vs_health",
        "avi_pool_member_health",
        "avi_latency",
        "avi_error_rates",
        "avi_se_state",
    ],
    "goad-vcf-mcp": [
        "vcf_inventory",
        "vcf_list_vms",
        "vcf_get_vm",
        "vcf_list_datastores",
        "vcf_get_datastore",
        "vcf_list_alerts",
        "vcf_vm_disk_latency",
    ],
}
CLIENTS = {
    "py-goad-incident-response": None,
    "py-goad-lb": "goad-avi-mcp",
    "py-goad-k8s": "goad-k8s-mcp",
    "py-goad-vcf": "goad-vcf-mcp",
}
HOST_FOR = {
    "goad-k8s-mcp": "K8S_MCP_HOST",
    "goad-avi-mcp": "AVI_MCP_HOST",
    "goad-vcf-mcp": "VCF_MCP_HOST",
}


def need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is unset")
    return value


class Am:
    def __init__(self, url: str, token: str, tenant_header: str, connect_ip: str, sni: str):
        self.url = url
        self.token = token
        self.tenant_header = tenant_header
        self.connect_ip = connect_ip
        self.sni = sni
        self.ctx = ssl._create_unverified_context()

    def call(self, tool: str, arguments: dict) -> dict:
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}
        ).encode()
        req = urllib.request.Request(self.url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("x-tenant-name", self.tenant_header)
        req.add_header("Host", self.sni)
        try:
            with self._open(req) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
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
                parsed = {"raw": parsed[:800]}
        if isinstance(parsed, dict) and (parsed.get("errorMessage") or parsed.get("errorCode")):
            raise SystemExit(
                f"{tool} failed {parsed.get('errorCode') or ''} {str(parsed.get('errorMessage') or '')[:200]}"
            )
        return parsed

    def _open(self, req: urllib.request.Request):
        dest = self.connect_ip
        sni = self.sni
        ctx = self.ctx

        class Handler(urllib.request.HTTPSHandler):
            def https_open(self, request):
                def mk(host, timeout=None, source_address=None):
                    class Conn(urllib.request.http.client.HTTPSConnection):
                        def connect(self):
                            sock = socket.create_connection((dest, 443), self.timeout)
                            self.sock = ctx.wrap_socket(sock, server_hostname=sni)

                    return Conn(host, timeout=timeout, context=ctx)

                return self.do_open(mk, request)

        return urllib.request.build_opener(Handler()).open(req, timeout=60)


def rows_named(doc) -> dict[str, dict]:
    rows = doc if isinstance(doc, list) else []
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("name") or row.get("policyName")
        if key:
            found[key] = row
    return found


def intents(tools: list[str]) -> list[str]:
    return [tool if tool.startswith("urn:") else INTENT + tool for tool in tools]


def scopes_for(tools: list[str]) -> list[dict]:
    rows = []
    for tool in tools:
        rows.append(
            {
                "scope": tool,
                "description": tool,
                "label": tool,
                "consentRequired": False,
                "isDefaultScope": True,
                "risk": "normal",
            }
        )
        rows.append(
            {
                "scope": INTENT + tool,
                "description": f"intent {tool}",
                "label": tool,
                "consentRequired": False,
                "isDefaultScope": False,
                "risk": "normal",
            }
        )
    return rows


def gateway(host: str, app_id: str) -> str:
    token = base64.b64encode(app_id.encode("ascii")).decode("ascii").rstrip("=")
    return f"https://{host}/default/aigateway/v1/mcp/{token}"


def main() -> None:
    host = need("AGENTMINDER_HOST")
    token = need("AM_MCP_TOKEN")
    connect = need("AGENTMINDER_CONNECT_IP")
    am = Am(f"https://{host}/default/mcp", token, "default", connect, host)
    present = {}
    for name in NAMES:
        found = rows_named(am.call("get_all_apps", {"filter": f'name eq "{name}"'}))
        if name in found:
            present[name] = found[name].get("appId")
    if present:
        for name, app_id in present.items():
            print("exists", name, app_id)
        raise SystemExit("stop: a name already exists")

    redirect = [f"https://{host}/default/ui/v1/adminconsole/"]
    servers = {}
    for name, tools in SERVERS.items():
        backend = "http://" + need(HOST_FOR[name]) + "/mcp"
        body = {
            "status": "active",
            "name": name,
            "description": f"Goad MCP door {name}",
            "clientType": "CONFIDENTIAL",
            "allowedOpenIDScopes": ["openid", "profile", "email"],
            "allowedGrantTypes": [
                "client_credentials",
                "authorization_code",
                "urn:ietf:params:oauth:grant-type:jwt-bearer",
            ],
            "allowedOperations": ["introspect"],
            "userInfoEndpointResponseFormat": "PLAIN_JSON",
            "isResourceServerApp": True,
            "isAiResourceServerApp": True,
            "isOidcApp": True,
            "requireAccessControl": "tenant",
            "primaryAudience": backend,
            "secondaryAudiences": [backend],
            "mcpServerEndpoint": backend,
            "mcpIgnoreSslValidation": True,
            "mcpRequireAccessToken": True,
            "mcpDiscoverRequireAccessToken": True,
            "enforcePolicies": True,
            "redirectURIs": redirect,
            "resScope": f"urn:rs:{name}",
            "resourceServerScopes": scopes_for(tools),
            "agentToolBindings": [
                {"toolName": tool, "intentScope": INTENT + tool, "skill": "", "description": tool}
                for tool in tools
            ],
        }
        created = am.call("create_app", {"request": json.dumps(body)})
        if not isinstance(created, dict) or not created.get("appId"):
            raise SystemExit(f"create resource server {name} returned no appId")
        app_id = created["appId"]
        route = gateway(host, app_id)
        update = {
            "isAiResourceServerApp": True,
            "isResourceServerApp": True,
            "mcpServerEndpoint": backend,
            "primaryAudience": route,
            "secondaryAudiences": [backend],
            "mcpIgnoreSslValidation": True,
            "mcpRequireAccessToken": True,
            "mcpDiscoverRequireAccessToken": True,
            "enforcePolicies": True,
            "requireAccessControl": "tenant",
            "status": "active",
            "resScope": f"urn:rs:{name}",
            "resourceServerScopes": scopes_for(tools),
            "agentToolBindings": body["agentToolBindings"],
        }
        am.call("update_app", {"id": app_id, "request": json.dumps(update)})
        servers[name] = {"appId": app_id, "backend": backend, "gateway": route}
        print("created resource server", name, app_id)

    saved = {}
    clients = {}
    for name in CLIENTS:
        body = {
            "status": "active",
            "name": name,
            "description": f"Goad AgentMinder client {name}",
            "clientType": "CONFIDENTIAL",
            "requireAccessControl": "tenant",
            "allowedOpenIDScopes": ["openid", "email", "profile"],
            "redirectURIs": redirect,
            "allowedGrantTypes": [
                "client_credentials",
                "urn:ietf:params:oauth:grant-type:jwt-bearer",
            ],
            "allowedOperations": ["introspect"],
            "skewTimeSecs": 0,
            "userInfoEndpointResponseFormat": "PLAIN_JSON",
            "itEncryptionTarget": "NONE",
            "metadata": [{"name": "urn:iam:app:oauthAccessTokenExpirySecs", "value": "60"}],
        }
        created = am.call("create_app", {"request": json.dumps(body)})
        if not isinstance(created, dict) or not created.get("appId"):
            raise SystemExit(f"create client {name} returned no appId")
        clients[name] = created
        saved[name] = {
            "appId": created.get("appId"),
            "clientId": created.get("clientId"),
            "secret": created.get("secret") or created.get("clientSecret") or "",
        }
        print("created client", name, created.get("appId"))

    policies = rows_named(am.call("get_all_authz_policies", {"filter": 'policyName eq "AuthClientPolicy"'}))
    auth = policies.get("AuthClientPolicy")
    if not auth or not auth.get("policyId"):
        raise SystemExit("AuthClientPolicy is missing")
    for name, client in clients.items():
        am.call(
            "grant_admin_role",
            {
                "request": json.dumps(
                    {
                        "id": auth["policyId"],
                        "principal": {"clientApp": {"operator": "in", "value": [client["appId"]]}},
                    }
                )
            },
        )
        print("auth client", name)

    for name, server_name in CLIENTS.items():
        if not server_name:
            print("no door", name)
            continue
        tools = SERVERS[server_name]
        role_name = name
        role = am.call(
            "create_authz_policy",
            {
                "request": json.dumps(
                    {
                        "policyName": role_name,
                        "description": f"Goad grant {role_name}",
                        "displayName": role_name,
                        "status": "active",
                        "apps": [{"id": servers[server_name]["appId"]}],
                        "rules": [
                            {
                                "conditions": {},
                                "result": {"effect": "grant", "msg": role_name, "privileges": intents(tools)},
                            }
                        ],
                    }
                )
            },
        )
        policy_id = role.get("policyId") if isinstance(role, dict) else None
        if not policy_id:
            raise SystemExit(f"create role {role_name} returned no policyId")
        am.call(
            "grant_app_role",
            {
                "request": json.dumps(
                    {
                        "id": policy_id,
                        "principal": {"clientApp": {"operator": "in", "value": [clients[name]["appId"]]}},
                    }
                )
            },
        )
        print("granted", name, server_name, policy_id)

    out = {
        "servers": servers,
        "clients": saved,
    }
    path = Path("/tmp/goad-am-clients.json")
    path.write_text(json.dumps(out, indent=2) + "\n")
    path.chmod(0o600)
    print("wrote", path)


if __name__ == "__main__":
    main()
