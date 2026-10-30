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

variable "cloud_admin_username" {
  type        = string
  description = "Username of the org's first administrator, for the cloud admin."
  default     = "cloud-admin"
}

variable "cloud_admin_password" {
  type        = string
  description = "Password for cloud_admin_username. The team's shared password."
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

# --- VCF SSO ---

variable "vcf_sso" {
  type        = bool
  description = "Log in to the org with VCF SSO, through the VCF Identity Broker. False leaves the org with its local user only."
  default     = true
}

variable "vidb_hostname" {
  type        = string
  description = "Host name of the VCF Identity Broker that holds the org's OIDC client."
}

variable "ops_url" {
  type        = string
  description = "VCF Operations URL, for example https://ops.lab.example. Terraform creates the org's OIDC client through it."
}

variable "ops_username" {
  type        = string
  description = "VCF Operations local administrator."
  default     = "admin"
}

variable "ops_password" {
  type        = string
  description = "Password for ops_username."
  sensitive   = true
}

variable "harbor_url" {
  type        = string
  description = "URL of the Supervisor's Harbor, the address of its harbor-nginx LoadBalancer, for example https://10.0.0.10."
}

variable "harbor_admin_username" {
  type        = string
  description = "Harbor's local administrator."
  default     = "admin"
}

variable "harbor_admin_password" {
  type        = string
  description = "Password for harbor_admin_username."
  sensitive   = true
}

variable "broadcom_registry_username" {
  type        = string
  description = "User of the Broadcom registry token: the Broadcom support portal email it was made for."
  sensitive   = true
}

variable "broadcom_registry_token" {
  type        = string
  description = "Broadcom registry token for tanzu-platform-content.packages.broadcom.com. Harbor's proxy cache logs in with it."
  sensitive   = true
}

variable "music_store_robot_secret" {
  type        = string
  description = "Secret of the Harbor robot account robot$music-store+builder: 8 to 128 characters, with an upper case letter, a lower case letter and a digit."
  sensitive   = true
  ephemeral   = true
}

variable "music_store_robot_secret_version" {
  type        = number
  description = "Raise by one to make Terraform set a new music_store_robot_secret on the robot account. Terraform cannot see the secret itself."
  default     = 1
}
