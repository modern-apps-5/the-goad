# The cloud admin's second stage works inside the org that
# terraform/cloud-admin/org created, as the org's one local user, an
# Organization Administrator. VCF Automation allows one local user per org;
# everyone else logs in with VCF SSO.
provider "vcfa" {
  url                  = var.vcfa_url
  org                  = var.org_name
  user                 = var.cloud_admin_username
  password             = var.cloud_admin_password
  allow_unverified_ssl = var.allow_unverified_ssl
}

# TerraCurl calls the VCF Automation REST API for what the vcfa provider
# does not cover, such as importing VCF SSO users. This login runs on every
# plan, apply, and destroy, so the token is always fresh.
data "http" "vcfa_session" {
  url      = "${local.vcfa_api}/1.0.0/sessions"
  method   = "POST"
  insecure = var.allow_unverified_ssl
  request_headers = {
    Accept        = local.vcfa_accept
    Authorization = "Basic ${base64encode("${var.cloud_admin_username}@${var.org_name}:${var.cloud_admin_password}")}"
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

# The org's Kubernetes API in VCF Automation. Projects and their role
# bindings are objects there.
data "vcfa_kubeconfig" "org" {}

provider "kubectl" {
  alias            = "org"
  host             = data.vcfa_kubeconfig.org.host
  token            = data.vcfa_kubeconfig.org.token
  insecure         = data.vcfa_kubeconfig.org.insecure_skip_tls_verify
  load_config_file = false
}
