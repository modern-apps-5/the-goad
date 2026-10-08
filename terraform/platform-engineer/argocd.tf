# Manifest 9: the Argo CD instance, applied as written in manifests/.
resource "kubectl_manifest" "argocd" {
  provider           = kubectl.platform
  yaml_body          = file("${path.module}/manifests/argocd.yaml")
  override_namespace = vcfa_supervisor_namespace.namespaces["platform"].name
  validate_schema    = false
}

locals {
  argocd_name = yamldecode(file("${path.module}/manifests/argocd.yaml")).metadata.name
}

# --- The Argo CD instance's VCF Automation service account ---
#
# The service creates the account with no role, and Argo CD then cannot
# register any namespace ("No assigned roles"). The portal adds the role
# when the instance is created there; through the API it is our job.
#
# Roles belong to the VCF Automation REST API, not to Kubernetes, so this
# part uses TerraCurl.

locals {
  namespace_api = "${data.vcfa_kubeconfig.platform.host}/api/v1/namespaces/${vcfa_supervisor_namespace.namespaces["platform"].name}"
  cloudapi      = "${trimsuffix(var.vcfa_url, "/")}/cloudapi/1.0.0"
  cloudapi_headers = {
    Accept        = "application/json;version=9.1.0"
    Authorization = "Bearer ${data.vcfa_kubeconfig.org.token}"
  }
}

# The account's Secret appears when the account exists. Until then this
# gets 404 and retries.
resource "terracurl_request" "argocd_service_account_ready" {
  name               = "argocd-service-account-ready"
  method             = "GET"
  url                = "${local.namespace_api}/secrets/${local.argocd_name}-argocd-vcfa-sa-secret"
  headers_wo         = { Authorization = "Bearer ${data.vcfa_kubeconfig.platform.token}" }
  headers_wo_version = 1
  response_codes     = ["200"]
  response_sensitive = true
  max_retry          = 60
  retry_interval     = 10
  skip_tls_verify    = data.vcfa_kubeconfig.platform.insecure_skip_tls_verify
  skip_destroy       = true

  depends_on = [kubectl_manifest.argocd]
}

data "terracurl_request" "argocd_status" {
  name            = "argocd-status"
  method          = "GET"
  url             = "${data.vcfa_kubeconfig.platform.host}/apis/argocd-service.vsphere.vmware.com/v1alpha1/namespaces/${vcfa_supervisor_namespace.namespaces["platform"].name}/argocds/${local.argocd_name}"
  headers         = { Authorization = "Bearer ${data.vcfa_kubeconfig.platform.token}" }
  response_codes  = ["200"]
  skip_tls_verify = data.vcfa_kubeconfig.platform.insecure_skip_tls_verify

  depends_on = [terracurl_request.argocd_service_account_ready]
}

locals {
  argocd_service_account_id = jsondecode(data.terracurl_request.argocd_status.response).status.serviceAccounts.platform.id
}

ephemeral "terracurl_request" "argocd_role" {
  name               = "argocd-role"
  method             = "GET"
  url                = "${local.cloudapi}/roles"
  request_parameters = { filter = "name==ArgoCD Instance" }
  headers            = local.cloudapi_headers
  response_codes     = ["200"]
  skip_tls_verify    = var.allow_unverified_ssl
  skip_renew         = true
  skip_close         = true
}

ephemeral "terracurl_request" "argocd_service_account" {
  name            = "argocd-service-account"
  method          = "GET"
  url             = "${local.cloudapi}/serviceAccounts/${local.argocd_service_account_id}"
  headers         = local.cloudapi_headers
  response_codes  = ["200"]
  skip_tls_verify = var.allow_unverified_ssl
  skip_renew      = true
  skip_close      = true
}

locals {
  argocd_role = {
    name = jsondecode(ephemeral.terracurl_request.argocd_role.response).values[0].name
    id   = jsondecode(ephemeral.terracurl_request.argocd_role.response).values[0].id
  }
}

# Sends the account back with the role added. Sent again only when the
# account changes.
resource "terracurl_request" "argocd_service_account_role" {
  name       = "argocd-service-account-role"
  method     = "PUT"
  url        = "${local.cloudapi}/serviceAccounts/${local.argocd_service_account_id}"
  headers_wo = merge(local.cloudapi_headers, { "Content-Type" = "application/json" })
  request_body_wo = jsonencode(merge(jsondecode(ephemeral.terracurl_request.argocd_service_account.response), {
    roles = concat(
      [for role in jsondecode(ephemeral.terracurl_request.argocd_service_account.response).roles : role if role.id != local.argocd_role.id],
      [local.argocd_role],
    )
  }))
  request_body_wo_version = parseint(substr(sha1(local.argocd_service_account_id), 0, 8), 16)
  headers_wo_version      = parseint(substr(sha1(local.argocd_service_account_id), 0, 8), 16)
  response_codes          = ["200"]
  skip_tls_verify         = var.allow_unverified_ssl
  skip_destroy            = true
}
