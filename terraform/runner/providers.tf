# The runner is not in VCF Automation: see decision 25. This root logs in to
# vCenter, and to the Supervisor with the same login.
provider "vsphere" {
  vsphere_server       = var.vcenter_server
  user                 = var.vcenter_user
  password             = var.vcenter_password
  allow_unverified_ssl = var.allow_unverified_ssl
}

# The Supervisor gives a session token for a vCenter login. It is what
# `vcf context refresh` gets. Terraform gets a new one on every run, so an
# expired session on your machine does not matter here.
data "http" "supervisor_login" {
  url      = "https://${var.supervisor_endpoint}/wcp/login"
  method   = "POST"
  insecure = var.allow_unverified_ssl

  request_headers = {
    Authorization = "Basic ${base64encode("${var.vcenter_user}:${var.vcenter_password}")}"
  }

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "The Supervisor refused the vCenter login: HTTP ${self.status_code}."
    }
  }
}

provider "kubectl" {
  host             = "https://${var.supervisor_endpoint}:6443"
  token            = jsondecode(data.http.supervisor_login.response_body).session_id
  insecure         = var.allow_unverified_ssl
  load_config_file = false
}
