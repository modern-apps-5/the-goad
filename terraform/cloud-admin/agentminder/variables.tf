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
  description = "Host name AgentMinder answers on. It must be in goad.gpu.set.lab, the zone Avi DNS serves, for the record to be made by itself."
}

variable "ssp_chart_version" {
  type        = string
  description = "Version of the charts ssp and ssp-infra. They are released together."
  default     = "4.1.1+1673"
}

variable "ingress_nginx_chart_version" {
  type        = string
  description = "Version of the ingress-nginx chart."
  default     = "4.15.1"
}

variable "ssp_registry_username" {
  type        = string
  description = "User for Broadcom's AgentMinder image registry, securityservices.packages.broadcom.com."
  sensitive   = true
}

variable "ssp_registry_password" {
  type        = string
  description = "Password for ssp_registry_username."
  sensitive   = true
}

variable "storage_class_name" {
  type        = string
  description = "StorageClass in the cluster that this root makes the default. The same as storage_class_name in terraform/cloud-admin/org-config."
}
