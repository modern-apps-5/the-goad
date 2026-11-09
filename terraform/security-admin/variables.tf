# --- NSX Manager login ---

variable "nsx_manager" {
  type        = string
  description = "NSX Manager host name, for example nsx01.lab.example"
}

variable "nsx_username" {
  type        = string
  description = "NSX user the security admin's Terraform logs in as."
}

variable "nsx_password" {
  type        = string
  description = "Password for nsx_username. The GitHub secret SECURITY_ADMIN_NSX_PASSWORD."
  sensitive   = true
}

variable "allow_unverified_ssl" {
  type        = bool
  description = "Skip TLS verification for NSX Manager."
  default     = false
}

# --- The cluster the policy reaches ---

variable "supervisor_namespace_prefix" {
  type        = string
  description = "The music store's Supervisor Namespace name before its generated suffix, as terraform/platform-engineer makes it."
  default     = "music-store"
}

variable "cluster_name" {
  type        = string
  description = "Name of the shop's VKS cluster, as in gitops/music-store/cluster.yaml."
  default     = "music-store"
}

variable "music_store_namespace" {
  type        = string
  description = "Kubernetes namespace of the shop inside the VKS cluster."
  default     = "music-store"
}

# --- Distributed IDPS on the users VM ---

variable "nsx_project_name" {
  type        = string
  description = "Display name of the goad org's NSX project, where the users VM's IDPS policy goes."
  default     = "goad"
}

variable "idps_cluster_config_id" {
  type        = string
  description = "NSX IDPS cluster config of the region's vSphere cluster, <vCenter UUID>:<cluster MoRef>. The plan stops if IDPS is off there."
}

# --- What may reach the shop's front end ---

variable "frontend_source_cidrs" {
  type        = list(string)
  description = "Addresses the shop's front end takes traffic from: the data network of the org's Avi service engines."

  # An empty source list in an NSX rule means any source.
  validation {
    condition     = length(var.frontend_source_cidrs) > 0
    error_message = "frontend_source_cidrs must name at least one address; an empty list allows any source."
  }
}
