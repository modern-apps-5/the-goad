# The cloud admin works in the provider (System) org. Everything in this
# root is provider scope. Tenant scope starts at the outputs.
#
# Login is user and password, not an API token. VCF Automation does not let
# an API token session create users, and org.tf creates one.
provider "vcfa" {
  url                  = var.vcfa_url
  org                  = "System"
  user                 = var.vcfa_user
  password             = var.vcfa_password
  allow_unverified_ssl = var.allow_unverified_ssl
}

# TerraCurl covers the one API the vcfa provider does not: see networking.tf.
# It needs a bearer token. This login runs on every plan, apply, and destroy,
# so the token is always fresh.
data "http" "vcfa_session" {
  url      = "${local.vcfa_api}/1.0.0/sessions/provider"
  method   = "POST"
  insecure = var.allow_unverified_ssl
  request_headers = {
    Accept        = local.vcfa_accept
    Authorization = "Basic ${base64encode("${var.vcfa_user}@System:${var.vcfa_password}")}"
  }

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "VCF Automation login failed with status ${self.status_code}."
    }
  }
}

locals {
  vcfa_api    = "${trimsuffix(var.vcfa_url, "/")}/cloudapi"
  vcfa_accept = "application/json;version=9.1.0"
  vcfa_token = sensitive(one([
    for name, value in data.http.vcfa_session.response_headers : value
    if lower(name) == "x-vmware-vcloud-access-token"
  ]))
}

# default_headers are read from this block on every run. Headers set on a
# resource are read from state at destroy, and the token there has expired.
provider "terracurl" {
  default_headers = {
    Accept        = local.vcfa_accept
    Authorization = "Bearer ${local.vcfa_token}"
  }
}
