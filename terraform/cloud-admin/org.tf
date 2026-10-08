resource "vcfa_org" "this" {
  name         = var.org_name
  display_name = var.org_display_name
  description  = "GOAD tenant. Managed by terraform/cloud-admin."
  is_enabled   = true
}

data "vcfa_role" "org_admin" {
  org_id = vcfa_org.this.id
  name   = "Organization Administrator"
}

# The first organization administrator. The platform engineer logs in as
# this user to create an API token. It also stays as the login that works
# when the identity provider does not.
resource "vcfa_org_local_user" "admin" {
  org_id   = vcfa_org.this.id
  role_ids = [data.vcfa_role.org_admin.id]
  username = var.org_admin_username
  password = var.org_admin_password
}
