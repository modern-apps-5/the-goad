# One OIDC configuration per org. Skipped when var.oidc is null, so the
# rest of the foundation applies before the identity provider is ready.
resource "vcfa_org_oidc" "this" {
  count = var.oidc == null ? 0 : 1

  org_id             = vcfa_org.this.id
  enabled            = true
  wellknown_endpoint = var.oidc.wellknown_endpoint
  client_id          = var.oidc.client_id
  client_secret      = var.oidc_client_secret
  prefer_id_token    = var.oidc.prefer_id_token
  ui_button_label    = var.oidc.ui_button_label
}
