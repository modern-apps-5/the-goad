# --- VCF Automation login ---

variable "vcfa_url" {
  type        = string
  description = "VCF Automation URL, for example https://vcfa.lab.example"
}

variable "allow_unverified_ssl" {
  type        = bool
  description = "Skip TLS verification for the VCF Automation endpoint."
  default     = false
}

variable "org_name" {
  type        = string
  description = "Org that terraform/cloud-admin/org created. Its output org_name."
  default     = "goad"
}

variable "cloud_admin_username" {
  type        = string
  description = "The org's one local user, an Organization Administrator, that terraform/cloud-admin/org created. Its output cloud_admin_username."
  default     = "cloud-admin"
}

variable "cloud_admin_password" {
  type        = string
  description = "Password for cloud_admin_username. The team's shared password, the same as in terraform/cloud-admin/org."
  sensitive   = true
}

# --- Who may do what in the org ---

variable "platform_engineers" {
  type        = set(string)
  description = "VCF SSO users, as user@domain, who get the org role Organization User and the role admin in platform_engineer_project."
  default     = []
}

variable "platform_engineer_project" {
  type        = string
  description = "Project the platform engineers administer. The org's default project holds their namespaces."
  default     = "default-project"
}

variable "platform_engineer_automation_user" {
  type        = string
  description = "VCF SSO user, as user@domain, whose API token terraform/platform-engineer logs in with. An AD service account. It gets the org role Organization Administrator. Null skips it."
  default     = null
}
