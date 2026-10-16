# The platform engineer works inside the org the cloud admin created. This
# root never logs in to the provider (System) org.
#
# It logs in with a user API token of an AD service account that
# terraform/cloud-admin/org-config imports as an Organization Administrator
# (platform_engineer_automation_user). People log in with VCF SSO.
provider "vcfa" {
  url                  = var.vcfa_url
  org                  = var.org_name
  auth_type            = "api_token"
  api_token            = var.vcfa_api_token
  allow_unverified_ssl = var.allow_unverified_ssl
}

# The org's Kubernetes API in VCF Automation. argocd.tf calls it with
# this token.
data "vcfa_kubeconfig" "org" {}

# The Kubernetes API of the namespace that holds Argo CD. The namespace
# name is generated, so its address is known only during apply. lazy_load
# lets the provider plan without it.
data "vcfa_kubeconfig" "platform" {
  project_name              = var.project_name
  supervisor_namespace_name = local.namespace_names["platform"]
}

provider "kubectl" {
  alias            = "platform"
  host             = data.vcfa_kubeconfig.platform.host
  token            = data.vcfa_kubeconfig.platform.token
  insecure         = data.vcfa_kubeconfig.platform.insecure_skip_tls_verify
  load_config_file = false
  lazy_load        = true
}
