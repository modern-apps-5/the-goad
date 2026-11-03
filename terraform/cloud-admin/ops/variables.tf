variable "ops_url" {
  type        = string
  description = "VCF Operations URL, for example https://ops.lab.example."
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

variable "allow_unverified_ssl" {
  type        = bool
  description = "Skip TLS verification for the VCF Operations endpoint."
  default     = false
}

variable "node_disk_latency_threshold_ms" {
  type        = number
  description = "Write latency of a VKS node VM's virtual disk, in milliseconds, above which the alert in alerts.tf fires."
  default     = 30
}
