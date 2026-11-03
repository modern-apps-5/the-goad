# Everything in this root goes through the VCF Operations API with
# TerraCurl: no provider covers alert definitions or the platform
# observability extension's dashboards. This login runs on every plan,
# apply, and destroy, so the token is always fresh.
data "http" "ops_session" {
  url      = "${local.ops_api}/auth/token/acquire"
  method   = "POST"
  insecure = var.allow_unverified_ssl
  request_headers = {
    Accept         = "application/json"
    "Content-Type" = "application/json"
  }
  request_body = jsonencode({
    username = var.ops_username
    password = var.ops_password
  })

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "VCF Operations login failed with status ${self.status_code}."
    }
  }
}

locals {
  ops_api       = "${trimsuffix(var.ops_url, "/")}/suite-api/api"
  ops_internal  = "${trimsuffix(var.ops_url, "/")}/suite-api/internal"
  ops_token     = sensitive(jsondecode(data.http.ops_session.response_body).token)
  ops_auth      = "OpsToken ${local.ops_token}"
  ops_unsupport = { "X-vRealizeOps-API-use-unsupported" = "true" }
}

# Headers come from this block on every run, so destroy uses a fresh token
# and not one stored in state. The internal API (the dashboards) also needs
# X-vRealizeOps-API-use-unsupported; the public API ignores it.
provider "terracurl" {
  default_headers = merge(local.ops_unsupport, {
    Accept        = "application/json"
    Authorization = local.ops_auth
  })
}
