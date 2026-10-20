# Who may do what in the org. Platform engineers are the members of one
# VCF SSO group, not users named one by one: they administer one project,
# not the whole org, and author kro APIs.
#
# A group must be in the org before a project can name it, so it is
# imported first with the org role Organization User. That role alone
# shows nothing; the project role bindings give the access. A member
# becomes a user of the org at the first login.
#
# The vcfa provider cannot import a VCF SSO user or group
# (vcfa_org_local_user is for local users only), so TerraCurl calls the
# VCF Automation API.

# The org roles this file gives, by name.
data "terracurl_request" "org_roles" {
  for_each = toset(["Organization User", "Organization Administrator"])

  name               = "org-role-${lower(replace(each.key, " ", "-"))}"
  method             = "GET"
  url                = "${local.vcfa_api}/1.0.0/roles"
  request_parameters = { filter = "name==${each.key}" }
  response_codes     = ["200"]
  skip_tls_verify    = var.allow_unverified_ssl

  lifecycle {
    postcondition {
      condition     = length(jsondecode(self.response).values) == 1
      error_message = "The org has no role named ${each.key}."
    }
  }
}

locals {
  org_roles = {
    for name, role in data.terracurl_request.org_roles : name => {
      id   = jsondecode(role.response).values[0].id
      name = jsondecode(role.response).values[0].name
    }
  }
}

# --- The platform engineer group ---

# Imports the group. It must be provisioned in the Identity Broker first.
# Destroy removes the group from the org.
resource "terracurl_request" "platform_engineer_group" {
  name    = "platform-engineer-group"
  method  = "POST"
  url     = "${local.vcfa_api}/1.0.0/groups"
  headers = { "Content-Type" = "application/json" }
  request_body = jsonencode({
    name           = var.platform_engineer_group
    providerType   = "OAUTH"
    roleEntityRefs = [local.org_roles["Organization User"]]
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  # skip_destroy defaults to true. Without this line destroy sends nothing.
  skip_destroy            = false
  destroy_url             = "${local.vcfa_api}/1.0.0/groups/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}

# The group's role in each project: admin of the project that holds the
# platform engineers' namespaces, and editor of the kro author project
# (kro.tf). VCF Automation requires the name cci:group:<domain>:<group>
# for a group group@domain.
locals {
  platform_engineer_group_project_roles = {
    (var.platform_engineer_project) = "admin"
    (var.kro_authors_project)       = "edit"
  }
}

resource "kubectl_manifest" "platform_engineer_group_project_role_binding" {
  for_each = local.platform_engineer_group_project_roles

  provider        = kubectl.org
  validate_schema = false

  # The API refuses the last-applied annotation that a client-side apply
  # adds: "Annotation updates are not supported".
  server_side_apply = true

  yaml_body = yamlencode({
    apiVersion = "authorization.cci.vmware.com/v1alpha1"
    kind       = "ProjectRoleBinding"
    metadata = {
      name      = "cci:group:${split("@", var.platform_engineer_group)[1]}:${split("@", var.platform_engineer_group)[0]}"
      namespace = each.key
    }
    roleRef = {
      apiGroup = "authorization.cci.vmware.com"
      kind     = "ProjectRole"
      name     = each.value
    }
    subjects = [{
      kind = "Group"
      name = var.platform_engineer_group
    }]
  })

  depends_on = [terracurl_request.platform_engineer_group, kubectl_manifest.kro_authors_project]
}

moved {
  from = kubectl_manifest.kro_author_group_project_role_binding
  to   = kubectl_manifest.platform_engineer_group_project_role_binding["kro-authors"]
}

# Platform engineers were imported one by one before. Keep the users in
# the org, where group membership now gives them their roles, and only
# drop them from state. Their user role bindings in default-project are
# destroyed.
removed {
  from = terracurl_request.platform_engineer_user

  lifecycle {
    destroy = false
  }
}

# --- The platform engineer's automation login ---
#
# terraform/platform-engineer logs in with a user API token of this VCF SSO
# user, an AD service account. It is an Organization Administrator: the
# platform engineer owns Argo CD, and giving the Argo CD instance's service
# account its role needs rights over service accounts in the org.
#
# Not a VCF Automation service account: a service account's session has no
# rights over other service accounts, whatever its role, and that step
# fails with SERVICE_ACCOUNT_SIMPLE_VIEW. A user API token's session has
# them.
#
# The token is made by hand, once: log in to the org as this user with
# VCF SSO, then User Preferences, API Tokens.
resource "terracurl_request" "platform_engineer_automation_user" {
  count = var.platform_engineer_automation_user == null ? 0 : 1

  name    = "platform-engineer-automation-user"
  method  = "POST"
  url     = "${local.vcfa_api}/1.0.0/users"
  headers = { "Content-Type" = "application/json" }
  request_body = jsonencode({
    username       = var.platform_engineer_automation_user
    providerType   = "OAUTH"
    enabled        = true
    roleEntityRefs = [local.org_roles["Organization Administrator"]]
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  # skip_destroy defaults to true. Without this line destroy sends nothing.
  skip_destroy            = false
  destroy_url             = "${local.vcfa_api}/1.0.0/users/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}
