# --- VCF Automation login ---

variable "vcfa_url" {
  type        = string
  description = "VCF Automation URL, for example https://vcfa.lab.example"
}

variable "org_name" {
  type        = string
  description = "Org the cloud admin created. Output org_name of terraform/cloud-admin."
  default     = "goad"
}

variable "vcfa_user" {
  type        = string
  description = "Organization administrator username. Output org_admin_username of terraform/cloud-admin."
  default     = "platform-admin"
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

# --- What the cloud admin gave the org ---

variable "region_name" {
  type        = string
  description = "Region to place the VPC and namespaces in."
}

variable "zone_name" {
  type        = string
  description = "Region zone to place namespaces in."
}

variable "storage_class_name" {
  type        = string
  description = "Storage class for namespaces, by its Kubernetes name."
}

variable "service_engine_group_name" {
  type        = string
  description = "Name of the Avi Service Engine Group this root creates for the org."
  default     = "goad-se-group"
}

# --- Project and VPC ---

variable "project_name" {
  type        = string
  description = "Existing project that holds the namespaces."
  default     = "default-project"
}

variable "vpc_name" {
  type        = string
  description = "Existing VPC for the namespaces. The org's default VPC is named default-<region>."
}

# --- Namespaces ---

variable "namespaces" {
  type = map(object({
    description        = string
    class_name         = optional(string, "small")
    cpu_limit          = string
    cpu_reservation    = optional(string, "0M")
    memory_limit       = string
    memory_reservation = optional(string, "0Mi")
    storage_limit      = string
  }))
  description = "Supervisor Namespaces, keyed by name prefix. VCF Automation adds a suffix to each name."
  default = {
    # Argo CD.
    platform = {
      description   = "GOAD platform services. Managed by terraform/platform-engineer."
      cpu_limit     = "10000M"
      memory_limit  = "16Gi"
      storage_limit = "50Gi"
    }
    # Private AI Services, its models, and the DSM databases.
    #
    # Private AI Services runs as vSphere Pods, and a vSphere Pod's CPU and
    # memory requests are reservations. With no reservation here its pods
    # stay Pending. Broadcom recommends at least 5 GHz. The org's region
    # quota must allow this much reservation: see terraform/cloud-admin.
    private-ai = {
      description        = "GOAD Private AI Services and databases. Managed by terraform/platform-engineer."
      cpu_limit          = "80000M"
      cpu_reservation    = "15000M"
      memory_limit       = "256Gi"
      memory_reservation = "16Gi"
      storage_limit      = "500Gi"
    }
  }

  validation {
    condition     = contains(keys(var.namespaces), "platform")
    error_message = "namespaces must include \"platform\". Argo CD runs there."
  }
}

# --- GitOps ---

variable "gitops_repo" {
  type = object({
    url      = string
    revision = optional(string, "main")
  })
  description = "Git repository Argo CD syncs gitops/ from. An SSH URL when a deploy key is used."
  default = {
    url = "git@github.com:modern-apps-5/the-goad.git"
  }
}

variable "gitops_repo_ssh_key_file" {
  type        = string
  description = "Path to the private half of a read-only deploy key for gitops_repo. Null for a public repository."
  default     = null
}
