# --- VCF Automation login ---

variable "vcfa_url" {
  type        = string
  description = "VCF Automation URL, for example https://vcfa.lab.example"
}

variable "vcfa_user" {
  type        = string
  description = "Provider administrator username in the System org."
  default     = "admin"
}

variable "vcfa_password" {
  type        = string
  description = "Password for vcfa_user."
  sensitive   = true
}

variable "allow_unverified_ssl" {
  type        = bool
  description = "Skip TLS verification for the VCF Automation endpoint."
  default     = false
}

# --- Existing infrastructure, by the name VCF Automation shows ---

variable "region_name" {
  type        = string
  description = "Name of the existing region."
}

variable "distributed_vlan_connection_name" {
  type        = string
  description = "Name of the existing Distributed VLAN Connection the org uses for external traffic."
}

variable "vna_cluster_name" {
  type        = string
  description = "Name of the existing virtual network appliance cluster that runs the org's VPC services."
}

# --- Org ---

variable "org_name" {
  type        = string
  description = "Org name. It is part of the tenant login URL."
  default     = "goad"
}

variable "org_display_name" {
  type        = string
  description = "Org name shown in the UI."
  default     = "GOAD"
}

variable "org_log_name" {
  type        = string
  description = "Identifier for the org in NSX logs. 1 to 8 characters, unique across orgs."
  default     = "goad"

  validation {
    condition     = length(var.org_log_name) >= 1 && length(var.org_log_name) <= 8
    error_message = "org_log_name must be 1 to 8 characters."
  }
}

variable "org_admin_username" {
  type        = string
  description = "Username of the first organization administrator."
  default     = "platform-admin"
}

variable "org_admin_password" {
  type        = string
  description = "Password for org_admin_username."
  sensitive   = true
}

# --- Quota ---

variable "zone_allocations" {
  type = map(object({
    cpu_limit_mhz          = number
    cpu_reservation_mhz    = optional(number, 0)
    memory_limit_mib       = number
    memory_reservation_mib = optional(number, 0)
  }))
  description = "CPU and memory the org can use, keyed by region zone name."
}

variable "vm_class_names" {
  type        = set(string)
  description = "VM classes the org can use. Add a GPU class here to give the org GPU capacity."
}

variable "storage_policy_limits_mib" {
  type        = map(number)
  description = "Storage limit in MiB, keyed by storage policy name. Each key must be a storage policy the region offers."
}

# --- Avi load balancer ---

variable "avi_service_engine_group_quota" {
  type        = number
  description = "Service Engine quota the org gets for the Avi load balancer in this region. 0 leaves the load balancer off for the org."
  default     = 1
}

# --- Data Services Manager ---

variable "dsm_infrastructure_policy_names" {
  type        = list(string)
  description = "DSM infrastructure policies the org can place databases on. Empty skips the data service policy."
  default     = []
}

# --- OIDC ---

variable "oidc" {
  type = object({
    wellknown_endpoint = string
    client_id          = string
    prefer_id_token    = optional(bool, true)
    ui_button_label    = optional(string, "Sign in with SSO")
  })
  description = "OIDC identity provider for the org. Null skips OIDC."
  default     = null
}

variable "oidc_client_secret" {
  type        = string
  description = "OIDC client secret."
  sensitive   = true
  default     = null
}
