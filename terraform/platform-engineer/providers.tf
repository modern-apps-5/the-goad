# The platform engineer works inside the org the cloud admin created. This
# root never logs in to the provider (System) org.
provider "vcfa" {
  url                  = var.vcfa_url
  org                  = var.org_name
  user                 = var.vcfa_user
  password             = var.vcfa_password
  allow_unverified_ssl = var.allow_unverified_ssl
}

# The org's Kubernetes API in VCF Automation. Service Engine Groups are
# objects there.
data "vcfa_kubeconfig" "org" {}

provider "kubectl" {
  alias            = "org"
  host             = data.vcfa_kubeconfig.org.host
  token            = data.vcfa_kubeconfig.org.token
  insecure         = data.vcfa_kubeconfig.org.insecure_skip_tls_verify
  load_config_file = false
}

# The Kubernetes API of the namespace that holds Argo CD. The namespace
# name is generated, so its address is known only during apply. lazy_load
# lets the provider plan without it.
data "vcfa_kubeconfig" "platform" {
  project_name              = var.project_name
  supervisor_namespace_name = vcfa_supervisor_namespace.namespaces["platform"].name
}

provider "kubectl" {
  alias            = "platform"
  host             = data.vcfa_kubeconfig.platform.host
  token            = data.vcfa_kubeconfig.platform.token
  insecure         = data.vcfa_kubeconfig.platform.insecure_skip_tls_verify
  load_config_file = false
  lazy_load        = true
}
