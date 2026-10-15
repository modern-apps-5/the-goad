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

# --- What terraform/cloud-admin/org gave the org ---

variable "region_name" {
  type        = string
  description = "Region for the Service Engine Group and the AgentMinder namespace. Output region_name of terraform/cloud-admin/org."
}

variable "zone_name" {
  type        = string
  description = "Region zone for the Service Engine Group and the AgentMinder namespace. One of output zone_names of terraform/cloud-admin/org."
}

variable "vpc_name" {
  type        = string
  description = "Existing VPC for the AgentMinder namespace. The org's default VPC is named default-<region>."
}

variable "storage_class_name" {
  type        = string
  description = "Storage class for the AgentMinder namespace and cluster, by its Kubernetes name."
}

# --- Avi ---

variable "service_engine_group_name" {
  type        = string
  description = "Name of the org's Avi Service Engine Group, which this root creates. terraform/platform-engineer names it too."
  default     = "goad-se-group"
}

# --- AgentMinder: project, namespace, and cluster ---

variable "cloud_admin_project" {
  type        = string
  description = "Project this root creates for the cloud admin's own services. Platform engineers have no role in it."
  default     = "cloud-admin"
}

variable "agentminder_cluster" {
  type = object({
    name                 = optional(string, "agentminder")
    kubernetes_version   = optional(string, "v1.36.2+vmware.2")
    cluster_class        = optional(string, "builtin-generic-v3.7.0")
    control_plane_class  = optional(string, "best-effort-medium")
    worker_class         = optional(string, "best-effort-large")
    workers              = optional(number, 2)
    containerd_disk_size = optional(string, "50Gi")
  })
  description = "The VKS cluster AgentMinder runs on. The VM classes must be among output vm_class_names of terraform/cloud-admin/org."
  default     = {}
}
