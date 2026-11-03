# The agentic ops engineer registers the incident demo's agents and MCP
# servers in the AgentMinder that terraform/cloud-admin/agentminder
# installed.
#
# The login: the default tenant's admin OAuth client, which the ssp chart
# makes on its first install. The cloud admin copies it once into two
# repository secrets, from the Secret ssp-ssp-secret-defaulttenantclient in
# namespace ssp. This root reads no cluster and no remote state. AgentMinder
# has no service accounts yet. See decisions 41 and 50.
locals {
  tenant_url = "https://${var.agentminder_hostname}/${var.tenant}"
}

# The token comes from this request, not from restapi's own
# oauth_client_credentials. restapi 3.0.0 hands the OAuth library a
# retryablehttp client where it expects a net/http one, so the token request
# falls back to Go's default client: it ignores insecure and root_ca_*, and
# fails on the chart's self-signed certificate. The Basic login and form body
# are the ones the AgentMinder Ansible modules send.
#
# A data source is read on every plan, a destroy's too, so the token is always
# new. It reaches the state, but expires within the hour.
#
# urn:iam:myscopes asks for every admin scope the client holds.
data "http" "agentminder_admin_token" {
  url      = "${local.tenant_url}/oauth2/v1/token"
  method   = "POST"
  insecure = var.insecure_skip_tls_verify
  request_headers = {
    Authorization  = "Basic ${base64encode("${urlencode(var.agentminder_client_id)}:${urlencode(var.agentminder_client_secret)}")}"
    "Content-Type" = "application/x-www-form-urlencoded"
  }
  request_body = "grant_type=client_credentials&scope=${urlencode("urn:iam:myscopes")}"

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "AgentMinder refused the admin client's token request (HTTP ${self.status_code})."
    }
  }
}

# restapi, not terracurl: the token is new on every run, so a destroy months
# later does not send an expired one from the state, and restapi reads each
# object back, so a change made in the console shows in the plan.
#
# Two configurations of the same login. The default one is for objects that
# AgentMinder names: a POST returns the new object, and its ID is read from
# that. The other, existing_id, is for writes to an object whose ID is known
# before the write. It reads the object back instead, so a response that is
# not the object does not fail the apply.
locals {
  restapi_headers = {
    "Authorization" = "Bearer ${sensitive(jsondecode(data.http.agentminder_admin_token.response_body).access_token)}"
    "Content-Type"  = "application/json"
    "Accept"        = "application/json"
  }
}

provider "restapi" {
  uri                   = local.tenant_url
  insecure              = var.insecure_skip_tls_verify
  headers               = local.restapi_headers
  create_returns_object = true

  # A PUT replaces the whole app. The client ID comes from AgentMinder, not
  # from the configuration, so it is copied from the app as it was read.
  copy_keys = ["clientId"]
}

provider "restapi" {
  alias     = "existing_id"
  uri       = local.tenant_url
  insecure  = var.insecure_skip_tls_verify
  headers   = local.restapi_headers
  copy_keys = ["clientId"]
}
