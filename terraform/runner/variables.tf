# --- vCenter login ---

variable "vcenter_server" {
  type        = string
  description = "vCenter address, for example vc01.lab.example"
}

variable "vcenter_user" {
  type        = string
  description = "A vCenter user that can create Supervisor Namespaces."
}

variable "vcenter_password" {
  type        = string
  description = "Password for vcenter_user."
  sensitive   = true
}

variable "allow_unverified_ssl" {
  type        = bool
  description = "Skip TLS verification for vCenter and the Supervisor."
  default     = false
}

# --- The Supervisor ---

variable "supervisor_endpoint" {
  type        = string
  description = "Address of the Supervisor's control plane."
}

variable "supervisor_id" {
  type        = string
  description = "Identifier of the Supervisor, from vCenter."
}

variable "storage_policy_name" {
  type        = string
  description = "vCenter storage policy that the namespace can use."
}

# --- The runner ---

variable "namespace_name" {
  type        = string
  description = "Name of the runner's Supervisor Namespace."
  default     = "goad-runner"
}

variable "github_app_id" {
  type        = string
  description = "ID of the GitHub App the runner logs in to GitHub with. Null: create the namespace only, and no runner."
  default     = null
}

variable "github_app_private_key_file" {
  type        = string
  description = "Path to the private key of the GitHub App."
  default     = ".secrets/private-key.pem"
}

variable "runner_commit" {
  type        = string
  description = "Commit of warroyo/supervisor-github-runner to take the runner from. A commit, not a branch: a branch would change the runner in an apply for something else."
}

variable "github_url" {
  type        = string
  description = "What the runner serves: an organization, https://github.com/<org>, or one repository."
}

variable "runner_labels" {
  type        = list(string)
  description = "The runner's labels. The workflows' runs-on must ask for these."
  default     = ["self-hosted", "lab"]
}

variable "runner_replicas" {
  type        = number
  description = "How many runners. One runner takes one job at a time."
  default     = 2
}

variable "runner_work_disk" {
  type        = string
  description = "Disk for a job's files: the checkout, the Terraform binary, and the providers. Deleted with the pod."
  default     = "4Gi"
}
