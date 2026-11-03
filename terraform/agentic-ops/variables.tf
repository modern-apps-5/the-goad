# --- AgentMinder ---

variable "agentminder_client_id" {
  type        = string
  description = "Client ID of AgentMinder's default tenant admin client. The cloud admin copies it once from the Secret ssp-ssp-secret-defaulttenantclient in namespace ssp. GitHub secret AGENTIC_OPS_AGENTMINDER_CLIENT_ID."
  sensitive   = true
}

variable "agentminder_client_secret" {
  type        = string
  description = "Secret of AgentMinder's default tenant admin client. The cloud admin copies it once from the Secret ssp-ssp-secret-defaulttenantclient in namespace ssp. GitHub secret AGENTIC_OPS_AGENTMINDER_CLIENT_SECRET."
  sensitive   = true
}

variable "incident_sidecar_token" {
  type        = string
  description = "Bearer token between each diagnostic agent and its AgentMinder sidecar. GitHub secret INCIDENT_SIDECAR_TOKEN; tanzu-apps.yml sets the same value as AGENTMINDER_SIDECAR_TOKEN."
  sensitive   = true
}

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
  description = "Skip TLS verification for AgentMinder and the CF API. Both have lab self-signed certificates."
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
  description = "The incident apps' space, which terraform/platform-engineer/tanzu.tf owns. Only read, except for the sc-* services in tools.tf."
  default     = "metal-music-app-agentic-system"
}
