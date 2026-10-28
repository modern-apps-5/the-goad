# --- VCF Automation login, to read the AgentMinder cluster's kubeconfig ---

variable "vcfa_url" {
  type        = string
  description = "VCF Automation URL, for example https://vcfa.lab.example"
}

variable "org_name" {
  type        = string
  description = "Org that terraform/cloud-admin/org created. Its output org_name."
  default     = "goad"
}

variable "cloud_admin_username" {
  type        = string
  description = "The org's one local user, an Organization Administrator. Output cloud_admin_username of terraform/cloud-admin/org."
  default     = "cloud-admin"
}

variable "cloud_admin_password" {
  type        = string
  description = "Password for cloud_admin_username. The team's shared password, the same as in terraform/cloud-admin/org."
  sensitive   = true
}

# --- AgentMinder ---

variable "agentminder_hostname" {
  type        = string
  description = "Host name AgentMinder answers on. The same as in terraform/cloud-admin/agentminder."
}

variable "tenant" {
  type        = string
  description = "AgentMinder tenant. The ssp chart makes only default."
  default     = "default"
}

variable "insecure_skip_tls_verify" {
  type        = bool
  description = "Skip TLS verification for VCF Automation, AgentMinder, and the CF API. All have lab self-signed certificates."
  default     = false
}

variable "apps_domain" {
  type        = string
  description = "Domain of the Cloud Foundry apps' routes. Each MCP server is https://metal-<name>-mcp.<apps_domain>/mcp."
}

variable "cf_api_url" {
  type        = string
  description = "CF API of the GOAD foundation."
  default     = "https://api.sys.goad.gpu.set.lab"
}

variable "cf_org_name" {
  type        = string
  description = "Org of the incident apps' space. Only read."
  default     = "Goad"
}

variable "cf_space_name" {
  type        = string
  description = "The incident apps' space, which terraform/platform-engineer/tanzu.tf owns. Only read."
  default     = "metal-music-app-agentic-system"
}
