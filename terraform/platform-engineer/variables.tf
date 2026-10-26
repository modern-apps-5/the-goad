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

variable "vcfa_api_token" {
  type        = string
  description = "VCF Automation API token of the platform engineer's AD service account (platform_engineer_automation_user in terraform/cloud-admin/org-config). Made by hand in the portal: User Preferences, API Tokens."
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
  description = "Name of the org's Avi Service Engine Group. terraform/cloud-admin/org-config creates it."
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
    # The shop's users VM, its DSM catalog, and the VKS cluster for its
    # containers. Best-effort VMs, so this namespace has no reservation.
    #
    # The cluster in gitops/music-store/cluster.yaml is three
    # best-effort-medium nodes (2 CPU, 8 GiB each), and the users VM is one
    # more VM. The storage limit leaves the org's 1 TiB region quota room
    # for the other namespaces.
    music-store = {
      description   = "GOAD music store: users VM, catalog database, and VKS cluster. Managed by terraform/platform-engineer."
      cpu_limit     = "40000M"
      memory_limit  = "48Gi"
      storage_limit = "150Gi"
    }
  }

  validation {
    condition     = contains(keys(var.namespaces), "platform") && contains(keys(var.namespaces), "private-ai")
    error_message = "namespaces must include \"platform\" and \"private-ai\". Terraform applies objects in both."
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

# --- VM images ---

variable "content_library_storage_policy" {
  type        = string
  description = "Storage policy for the org's content library, by its name in vCenter, not its Kubernetes name. The region quota of the org must include it."
}

variable "ubuntu_image" {
  type = object({
    name = optional(string, "ubuntu-24.04-cloud")
    url  = optional(string, "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.ova")
  })
  description = "The Ubuntu image in the org's content library. name is the imageName of the users VM in gitops/music-store-dev/users-vm/users-vm.yaml."
  default     = {}
}

# --- Private AI Services ---

variable "pais_admin_password_hash" {
  type        = string
  description = "SHA-512 crypt hash of the password for the Private AI Services user admin. Make one with: openssl passwd -6. Null skips the Secret."
  sensitive   = true
  default     = null
}
