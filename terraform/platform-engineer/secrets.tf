# The music store's secrets, in Secret Store (decision 38).
#
# The values are GitHub repository secrets, passed to the workflow as
# TF_VAR_*, or terraform.tfvars on a machine. Terraform writes them as
# KeyValueSecrets in the music-store Supervisor Namespace, which stores
# them in OpenBao, not in etcd. Then:
# - catalog-init (gitops/music-store) reads music-store-catalog through the
#   Supervisor's vault injector, and sets it on the database role;
# - ESO in the VKS cluster reads both into Secrets for the shop
#   (gitops/music-store-platform, gitops/music-store-dev/app).
#
# The names start with the cluster name: the role Secret Store makes for
# the cluster reads only those. Argo CD must never own a KeyValueSecret:
# the API ignores label selectors, so a pruning tool deletes every KV in
# the namespace.
data "vcfa_kubeconfig" "music_store" {
  project_name              = var.project_name
  supervisor_namespace_name = local.namespace_names["music-store"]
}

provider "kubectl" {
  alias            = "music_store"
  host             = data.vcfa_kubeconfig.music_store.host
  token            = data.vcfa_kubeconfig.music_store.token
  insecure         = data.vcfa_kubeconfig.music_store.insecure_skip_tls_verify
  load_config_file = false
  lazy_load        = true
}

locals {
  music_store_kv = {
    catalog = "${local.music_store_cluster_name}-catalog"
    chat    = "${local.music_store_cluster_name}-chat"
  }
}

resource "kubectl_manifest" "music_store_catalog_kv" {
  count    = nonsensitive(try(length(var.music_store_db_password), 0) == 0) ? 0 : 1
  provider = kubectl.music_store

  validate_schema  = false
  sensitive_fields = ["spec.data"]
  # The API never returns the values, so the live object cannot be
  # compared with them. A change to the variable still updates the KV.
  ignore_fields = ["spec.data"]
  yaml_body = yamlencode({
    apiVersion = "secretstore.vmware.com/v1alpha1"
    kind       = "KeyValueSecret"
    metadata = {
      name      = local.music_store_kv.catalog
      namespace = local.namespace_names["music-store"]
    }
    spec = {
      name = local.music_store_kv.catalog
      data = [{ key = "password", value = var.music_store_db_password }]
    }
  })
}

resource "kubectl_manifest" "music_store_chat_kv" {
  count    = nonsensitive(try(length(var.music_store_chat_api_key), 0) == 0) ? 0 : 1
  provider = kubectl.music_store

  validate_schema  = false
  sensitive_fields = ["spec.data"]
  ignore_fields    = ["spec.data"]
  yaml_body = yamlencode({
    apiVersion = "secretstore.vmware.com/v1alpha1"
    kind       = "KeyValueSecret"
    metadata = {
      name      = local.music_store_kv.chat
      namespace = local.namespace_names["music-store"]
    }
    spec = {
      name = local.music_store_kv.chat
      data = [
        { key = "base-url", value = var.music_store_chat.base_url },
        { key = "model", value = var.music_store_chat.model },
        { key = "api-key", value = var.music_store_chat_api_key },
      ]
    }
  })
}
