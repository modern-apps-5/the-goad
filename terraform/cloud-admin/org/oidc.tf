# Login to the org with VCF SSO: people sign in with their AD account
# through the VCF Identity Broker, the same way the provider (System) org
# does. An org can have only one local user, so every other person comes in
# this way.
#
# Two parts:
#
# 1. An OIDC client in the Identity Broker for this org. The portal's place
#    for it is VCF Operations, Fleet Management, Identity & Access, VCF SSO,
#    Other Components. Neither the vcfa provider nor any other provider can
#    make one. TerraCurl calls the VCF Operations API that the portal uses.
#    That API is internal: it needs the X-vRealizeOps-API-use-unsupported
#    header, and it can change in another release.
# 2. The org's OIDC setting, with that client.
#
# Skipped when var.vcf_sso is false.

# --- VCF Operations login ---
#
# A fresh token on every plan, apply, and destroy, like the VCF Automation
# login in providers.tf. The token is valid for a few hours.
data "http" "ops_session" {
  count = var.vcf_sso ? 1 : 0

  url      = "${trimsuffix(var.ops_url, "/")}/suite-api/api/auth/token/acquire"
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
  ops_vidb_api = "${trimsuffix(var.ops_url, "/")}/suite-api/internal/vidb"
  ops_token    = var.vcf_sso ? sensitive(jsondecode(data.http.ops_session[0].response_body).token) : ""
}

# Headers come from this block on every run, so destroy uses a fresh token
# and not one stored in state.
provider "terracurl" {
  alias = "ops"
  default_headers = {
    Accept                              = "application/json"
    "Content-Type"                      = "application/json"
    Authorization                       = "OpsToken ${local.ops_token}"
    "X-vRealizeOps-API-use-unsupported" = "true"
  }
}

# The Identity Broker's SSO domain. The client is created in it.
data "terracurl_request" "identity_providers" {
  count    = var.vcf_sso ? 1 : 0
  provider = terracurl.ops

  name            = "identity-providers"
  method          = "GET"
  url             = "${local.ops_vidb_api}/identityproviders"
  response_codes  = ["200"]
  skip_tls_verify = var.allow_unverified_ssl

  lifecycle {
    postcondition {
      condition = length([
        for idp in jsondecode(self.response).identityProviderInfoList : idp
        if idp.vidbHostname == var.vidb_hostname
      ]) == 1
      error_message = "VCF Operations has no identity provider on the Identity Broker ${var.vidb_hostname}."
    }
  }
}

locals {
  sso_domain_id = var.vcf_sso ? one([
    for idp in jsondecode(data.terracurl_request.identity_providers[0].response).identityProviderInfoList : idp.ssoDomainId
    if idp.vidbHostname == var.vidb_hostname
  ]) : ""

  # Where the Identity Broker sends a person back after login. VCF
  # Automation shows the same address for the org.
  org_redirect_uri = "${trimsuffix(var.vcfa_url, "/")}/login/oauth?service=tenant:${var.org_name}"
}

# --- The org's OIDC client in the Identity Broker ---
#
# The create answer holds the client ID and secret, so it is kept as a
# sensitive response. There is no call to read a client back, so this
# resource does not see a client changed in the portal. A change to the
# name or redirect address makes a new client and deletes the old one.
resource "terracurl_request" "org_oidc_client" {
  count    = var.vcf_sso ? 1 : 0
  provider = terracurl.ops

  name   = "org-oidc-client"
  method = "POST"
  url    = "${local.ops_vidb_api}/oauthclients"
  request_body = jsonencode({
    clientName   = "vcfa-org-${var.org_name}"
    ssoDomainId  = local.sso_domain_id
    redirectUris = [local.org_redirect_uri]
  })
  response_codes     = ["201"]
  response_sensitive = true
  skip_tls_verify    = var.allow_unverified_ssl

  # skip_destroy defaults to true. Without this line destroy sends nothing.
  skip_destroy               = false
  destroy_url                = "${local.ops_vidb_api}/oauthclients/{response.clientId}"
  destroy_method             = "DELETE"
  destroy_request_parameters = { ssoDomainId = local.sso_domain_id }
  destroy_response_codes     = ["204"]
  destroy_skip_tls_verify    = var.allow_unverified_ssl
}

locals {
  org_oidc_client = var.vcf_sso ? jsondecode(terracurl_request.org_oidc_client[0].sensitive_response) : null
}

# --- The org's OIDC setting ---
#
# Scopes and claims are the ones the provider (System) org uses with the
# same Identity Broker.
resource "vcfa_org_oidc" "vcf_sso" {
  count = var.vcf_sso ? 1 : 0

  org_id             = vcfa_org.this.id
  enabled            = true
  wellknown_endpoint = "${local.org_oidc_client.issuerUrl}/.well-known/openid-configuration"
  client_id          = local.org_oidc_client.clientId
  client_secret      = local.org_oidc_client.clientSecret
  scopes             = ["openid", "profile", "email", "group"]
  ui_button_label    = "VCF SSO"

  claims_mapping {
    subject    = "preferred_username"
    email      = "email"
    full_name  = "name"
    first_name = "given_name"
    last_name  = "family_name"
    groups     = "group_names"
    roles      = "roles"
  }
}
