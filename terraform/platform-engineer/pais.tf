# The login for Private AI Services: one local administrator.
#
# Argo CD creates Private AI Services from gitops/private-ai/. This Secret
# is the one piece it needs that cannot be in git.
data "vcfa_kubeconfig" "private_ai" {
  project_name              = var.project_name
  supervisor_namespace_name = vcfa_supervisor_namespace.namespaces["private-ai"].name
}

provider "kubectl" {
  alias            = "private_ai"
  host             = data.vcfa_kubeconfig.private_ai.host
  token            = data.vcfa_kubeconfig.private_ai.token
  insecure         = data.vcfa_kubeconfig.private_ai.insecure_skip_tls_verify
  load_config_file = false
  lazy_load        = true
}

resource "kubectl_manifest" "pais_static_credentials" {
  count    = var.pais_admin_password_hash == null ? 0 : 1
  provider = kubectl.private_ai

  sensitive_fields = ["stringData"]
  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Secret"
    metadata = {
      name      = "pais-static-credentials"
      namespace = vcfa_supervisor_namespace.namespaces["private-ai"].name
    }
    stringData = {
      "credentials.json" = jsonencode([{
        userID   = "admin"
        username = "admin"
        hash     = var.pais_admin_password_hash
      }])
    }
  })
}
