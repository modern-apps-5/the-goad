resource "vcfa_org" "this" {
  name         = var.org_name
  display_name = var.org_display_name
  description  = "GOAD tenant. Managed by terraform/cloud-admin/org."
  is_enabled   = true
}

data "vcfa_role" "org_admin" {
  org_id = vcfa_org.this.id
  name   = "Organization Administrator"
}

# The org's first administrator, for the cloud admin.
# terraform/cloud-admin/org-config logs in as this user to configure the
# org. It also stays as the login that works when the identity provider
# does not.
resource "vcfa_org_local_user" "cloud_admin" {
  org_id   = vcfa_org.this.id
  role_ids = [data.vcfa_role.org_admin.id]
  username = var.cloud_admin_username
  password = var.cloud_admin_password
}
