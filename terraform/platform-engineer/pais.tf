# The login for Private AI Services: one local administrator.
#
# Argo CD creates Private AI Services from gitops/private-ai/. This Secret
# is the one piece it needs that cannot be in git.
data "vcfa_kubeconfig" "private_ai" {
  project_name              = var.project_name
  supervisor_namespace_name = local.namespace_names["private-ai"]
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
      namespace = local.namespace_names["private-ai"]
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

# The GOAD CA, which cert-manager issues the Private AI Services ingress
# certificate from (gitops/private-ai/ingress.yaml). The key is the GitHub
# secret GOAD_CA_KEY; the certificate is public and in git. Made by
# scripts/goad-ca.sh. Until this Secret exists, the Certificate in sync
# wave 0 is not Ready, and Argo CD does not go on to Private AI Services.
resource "kubectl_manifest" "goad_ca" {
  count    = nonsensitive(try(length(var.goad_ca_key), 0) == 0) ? 0 : 1
  provider = kubectl.private_ai

  sensitive_fields = ["stringData"]
  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Secret"
    type       = "kubernetes.io/tls"
    metadata = {
      name      = "goad-ca"
      namespace = local.namespace_names["private-ai"]
    }
    stringData = {
      "tls.crt" = file("${path.module}/../../gitops/private-ai/goad-ca.crt")
      "tls.key" = var.goad_ca_key
    }
  })
}
