# For people. The apps get their clients from the am-* user-provided
# services (cloudfoundry.tf), not from these.

output "agent_clients" {
  description = "Client ID and MCP gateway URL of each diagnostic agent."
  value = {
    for k, c in local.diagnostic_clients : k => {
      client_id   = restapi_object.client[k].api_data["clientId"]
      gateway_url = local.gateway_urls[c.server]
    }
  }
}

output "mcp_servers" {
  description = "App ID and gateway URL of each MCP server."
  value = {
    for k, s in local.mcp_servers : k => {
      name        = s.name
      app_id      = restapi_object.mcp_server[k].id
      gateway_url = local.gateway_urls[k]
    }
  }
}
