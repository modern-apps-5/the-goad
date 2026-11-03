# The incident demo's AgentMinder objects, which incident-demo/agentminder/
# register.py used to make by hand:
#
#   MCP servers   goad-avi-mcp, goad-k8s-mcp, goad-vcf-mcp: AgentMinder
#                 resource servers in front of the metal-*-mcp apps. The
#                 agents call them through AgentMinder's gateway.
#   clients       py-goad-lb, py-goad-k8s, py-goad-vcf: one for each
#                 diagnostic agent. py-goad-incident-response has no MCP
#                 server.
#   policies      each diagnostic client may use its own server's tools,
#                 and every client is in AuthClientPolicy.
#
# The payloads follow the agentminder-mcp-demo Ansible modules: the whole app
# on every PUT, and the client named inside the policy's rule.

locals {
  intent_prefix = "urn:iam:agent:intent:"
  redirect_uris = ["${local.tenant_url}/ui/v1/adminconsole/"]

  # Each server's tools. Each tool is a scope and an intent of the same name.
  mcp_servers = {
    avi = {
      name = "goad-avi-mcp"
      tools = [
        "avi_vs_health",
        "avi_pool_member_health",
        "avi_latency",
        "avi_error_rates",
        "avi_se_state",
      ]
    }
    k8s = {
      name = "goad-k8s-mcp"
      tools = [
        "k8s_list_deployments",
        "k8s_list_pods",
        "k8s_events",
        "k8s_pod_logs",
        "k8s_list_namespaces",
      ]
    }
    vcf = {
      name = "goad-vcf-mcp"
      tools = [
        "vcf_inventory",
        "vcf_list_vms",
        "vcf_get_vm",
        "vcf_list_datastores",
        "vcf_get_datastore",
        "vcf_list_alerts",
        "vcf_vm_disk_latency",
      ]
    }
  }

  # The keys are the ones in tanzu/metal-music-app-agentic-system/manifest.yml:
  # am_<key>_client_id and so on.
  clients = {
    lb                = { name = "py-goad-lb", server = "avi" }
    k8s               = { name = "py-goad-k8s", server = "k8s" }
    vcf               = { name = "py-goad-vcf", server = "vcf" }
    incident_response = { name = "py-goad-incident-response", server = null }
  }

  diagnostic_clients = { for k, c in local.clients : k => c if c.server != null }

  mcp_server_apps = {
    for k, s in local.mcp_servers : k => {
      backend = "https://metal-${k}-mcp.${var.apps_domain}/mcp"
      body = {
        status                         = "active"
        name                           = s.name
        description                    = "Goad MCP server ${s.name}"
        clientType                     = "CONFIDENTIAL"
        allowedOpenIDScopes            = ["openid", "profile", "email"]
        allowedGrantTypes              = ["client_credentials", "authorization_code", "urn:ietf:params:oauth:grant-type:jwt-bearer"]
        allowedOperations              = ["introspect"]
        userInfoEndpointResponseFormat = "PLAIN_JSON"
        isOidcApp                      = true
        isResourceServerApp            = true
        isAiResourceServerApp          = true
        requireAccessControl           = "tenant"
        redirectURIs                   = local.redirect_uris
        mcpServerEndpoint              = "https://metal-${k}-mcp.${var.apps_domain}/mcp"
        secondaryAudiences             = ["https://metal-${k}-mcp.${var.apps_domain}/mcp"]
        # The apps' routes have the lab's self-signed certificate.
        mcpIgnoreSslValidation        = true
        mcpRequireAccessToken         = true
        mcpDiscoverRequireAccessToken = true
        enforcePolicies               = true
        resScope                      = "urn:rs:${s.name}"
        resourceServerScopes = flatten([
          for tool in s.tools : [
            { scope = tool, description = tool, label = tool, consentRequired = false, isDefaultScope = true, risk = "normal" },
            { scope = "${local.intent_prefix}${tool}", description = "intent ${tool}", label = tool, consentRequired = false, isDefaultScope = false, risk = "normal" },
          ]
        ])
        agentToolBindings = [
          for tool in s.tools : { toolName = tool, intentScope = "${local.intent_prefix}${tool}", skill = "", description = tool }
        ]
      }
    }
  }
}

# --- MCP servers ---

# The agents ask for tokens for the server's gateway route, so that is the
# primary audience. The route is made from the app's ID, which exists only
# after the create. So two resources: this one creates and deletes the app,
# with the backend as a first audience, and mcp_server_config below puts
# the whole app with the gateway route. This one never updates.
resource "restapi_object" "mcp_server" {
  for_each = local.mcp_server_apps

  path         = "/admin/v1/Apps"
  id_attribute = "appId"
  destroy_path = "/admin/v1/Apps/{id}?force=true"
  data = jsonencode(merge(each.value.body, {
    primaryAudience = each.value.backend
  }))

  # Not ignore_all_server_changes: with it, restapi plans the old response
  # for an update, so the response to the PUT fails the apply as an
  # inconsistent result. The first apply after the import updates this
  # object, to record destroy_path and id_attribute in the state.
  lifecycle {
    ignore_changes = [data]
  }
}

locals {
  # AgentMinder's gateway route for a resource server: its app ID, base64
  # without padding.
  gateway_urls = {
    for k, app in restapi_object.mcp_server :
    k => "${local.tenant_url}/aigateway/v1/mcp/${trimsuffix(base64encode(app.id), "=")}"
  }
}

resource "restapi_object" "mcp_server_config" {
  for_each = local.mcp_server_apps
  provider = restapi.existing_id

  path          = "/admin/v1/Apps"
  id_attribute  = "appId"
  create_method = "PUT"
  create_path   = "/admin/v1/Apps/{id}"
  # Removing the config leaves the app to mcp_server, which deletes it.
  destroy_method = "GET"
  data = jsonencode(merge(each.value.body, {
    appId           = restapi_object.mcp_server[each.key].id
    clientId        = restapi_object.mcp_server[each.key].api_data["clientId"]
    primaryAudience = local.gateway_urls[each.key]
  }))

  ignore_server_additions = true
}

# --- Clients ---

resource "restapi_object" "client" {
  for_each = local.clients

  path         = "/admin/v1/Apps"
  id_attribute = "appId"
  destroy_path = "/admin/v1/Apps/{id}?force=true"
  data = jsonencode({
    status                         = "active"
    name                           = each.value.name
    description                    = "Goad AgentMinder client ${each.value.name}"
    clientType                     = "CONFIDENTIAL"
    requireAccessControl           = "tenant"
    allowedOpenIDScopes            = ["openid", "email", "profile"]
    redirectURIs                   = local.redirect_uris
    allowedGrantTypes              = ["client_credentials", "urn:ietf:params:oauth:grant-type:jwt-bearer"]
    allowedOperations              = ["introspect"]
    skewTimeSecs                   = 0
    userInfoEndpointResponseFormat = "PLAIN_JSON"
    itEncryptionTarget             = "NONE"
    metadata                       = [{ name = "urn:iam:app:oauthAccessTokenExpirySecs", value = "60" }]
  })

  ignore_server_additions = true
}

# --- Policies ---

# Each diagnostic client may use every tool of its own MCP server.
resource "restapi_object" "client_role" {
  for_each = local.diagnostic_clients

  path         = "/admin/v1/AuthZPolicies"
  id_attribute = "policyId"
  data = jsonencode({
    policyName    = each.value.name
    displayName   = each.value.name
    description   = "Goad grant ${each.value.name}"
    policySubType = "role"
    status        = "active"
    matchAnyApp   = false
    apps = [{
      id   = restapi_object.mcp_server[each.value.server].id
      name = local.mcp_servers[each.value.server].name
    }]
    rules = [{
      conditions = { principal = { clientApp = { operator = "in", value = [restapi_object.client[each.key].id] } } }
      result = {
        effect     = "grant"
        msg        = each.value.name
        privileges = [for tool in local.mcp_servers[each.value.server].tools : "${local.intent_prefix}${tool}"]
      }
    }]
  })

  ignore_server_additions = true
}

# AuthClientPolicy is AgentMinder's own admin role policy. The clients are
# added to it as principals, and removed on destroy. The policy itself is
# not this root's.
data "restapi_object" "auth_client_policy" {
  path         = "/admin/v1/AuthZPolicies"
  search_key   = "policyName"
  search_value = "AuthClientPolicy"
  id_attribute = "policyId"
}

resource "restapi_object" "auth_client_grant" {
  for_each = local.clients
  provider = restapi.existing_id

  path          = "/admin/v1/AdminRolesDelegator"
  create_method = "POST"
  # The delegator returns no object to read. The client's app ID names the
  # grant, and the read is of the policy, which is never compared.
  object_id      = restapi_object.client[each.key].id
  id_attribute   = "grantId"
  read_path      = "/admin/v1/AuthZPolicies/${data.restapi_object.auth_client_policy.id}"
  destroy_path   = "/admin/v1/AdminRolesDelegator"
  destroy_method = "DELETE"
  data = jsonencode({
    id        = data.restapi_object.auth_client_policy.id
    principal = { clientApp = { operator = "in", value = [restapi_object.client[each.key].id] } }
  })
  destroy_data = jsonencode({
    id        = data.restapi_object.auth_client_policy.id
    principal = { clientApp = { operator = "in", value = [restapi_object.client[each.key].id] } }
  })

  ignore_all_server_changes = true
  force_new                 = ["id", "principal"]
}
