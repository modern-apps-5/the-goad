# One time only: adopt the apps and policies that
# incident-demo/agentminder/register.py made, so the running agents keep
# their client IDs and secrets. Each one is found by name. Delete this file
# after the first apply: on a new AgentMinder the lookups find nothing and
# fail the plan.
#
# restapi's import ID is the object's path. The grants in AuthClientPolicy
# are not imported: the first apply adds each client again.

data "restapi_object" "existing_mcp_server" {
  for_each = local.mcp_servers

  path         = "/admin/v1/Apps"
  search_key   = "name"
  search_value = each.value.name
  id_attribute = "appId"
}

data "restapi_object" "existing_client" {
  for_each = local.clients

  path         = "/admin/v1/Apps"
  search_key   = "name"
  search_value = each.value.name
  id_attribute = "appId"
}

data "restapi_object" "existing_client_role" {
  for_each = local.diagnostic_clients

  path         = "/admin/v1/AuthZPolicies"
  search_key   = "policyName"
  search_value = each.value.name
  id_attribute = "policyId"
}

import {
  for_each = local.mcp_servers
  to       = restapi_object.mcp_server[each.key]
  id       = "/admin/v1/Apps/${data.restapi_object.existing_mcp_server[each.key].id}"
}

import {
  for_each = local.mcp_servers
  to       = restapi_object.mcp_server_config[each.key]
  id       = "/admin/v1/Apps/${data.restapi_object.existing_mcp_server[each.key].id}"
}

import {
  for_each = local.clients
  to       = restapi_object.client[each.key]
  id       = "/admin/v1/Apps/${data.restapi_object.existing_client[each.key].id}"
}

import {
  for_each = local.diagnostic_clients
  to       = restapi_object.client_role[each.key]
  id       = "/admin/v1/AuthZPolicies/${data.restapi_object.existing_client_role[each.key].id}"
}
