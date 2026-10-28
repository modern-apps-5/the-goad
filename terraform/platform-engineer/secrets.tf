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

# --- The platform tools cluster's secrets (decision 42) ---
#
# Same path as the music store's: GitHub secret, Terraform, a KeyValueSecret
# in the platform-tools Supervisor Namespace, and ESO in the cluster
# (gitops/platform-tools-apps/external-secrets.yaml). The names start with
# the cluster name, for the same reason.
data "vcfa_kubeconfig" "platform_tools" {
  project_name              = var.project_name
  supervisor_namespace_name = local.namespace_names["platform-tools"]
}

provider "kubectl" {
  alias            = "platform_tools"
  host             = data.vcfa_kubeconfig.platform_tools.host
  token            = data.vcfa_kubeconfig.platform_tools.token
  insecure         = data.vcfa_kubeconfig.platform_tools.insecure_skip_tls_verify
  load_config_file = false
  lazy_load        = true
}

locals {
  platform_tools_kv = {
    grafana = "${local.platform_tools_cluster_name}-grafana"
    zammad  = "${local.platform_tools_cluster_name}-zammad"
    qwen    = "${local.platform_tools_cluster_name}-qwen"
  }
}

resource "kubectl_manifest" "platform_tools_grafana_kv" {
  count    = nonsensitive(try(length(var.incident_grafana_admin_password), 0) == 0) ? 0 : 1
  provider = kubectl.platform_tools

  validate_schema  = false
  sensitive_fields = ["spec.data"]
  ignore_fields    = ["spec.data"]
  yaml_body = yamlencode({
    apiVersion = "secretstore.vmware.com/v1alpha1"
    kind       = "KeyValueSecret"
    metadata = {
      name      = local.platform_tools_kv.grafana
      namespace = local.namespace_names["platform-tools"]
    }
    spec = {
      name = local.platform_tools_kv.grafana
      data = [{ key = "password", value = var.incident_grafana_admin_password }]
    }
  })
}

resource "kubectl_manifest" "platform_tools_zammad_kv" {
  count    = nonsensitive(try(length(var.incident_zammad_db_password), 0) == 0 || try(length(var.incident_zammad_admin_password), 0) == 0) ? 0 : 1
  provider = kubectl.platform_tools

  validate_schema  = false
  sensitive_fields = ["spec.data"]
  ignore_fields    = ["spec.data"]
  yaml_body = yamlencode({
    apiVersion = "secretstore.vmware.com/v1alpha1"
    kind       = "KeyValueSecret"
    metadata = {
      name      = local.platform_tools_kv.zammad
      namespace = local.namespace_names["platform-tools"]
    }
    spec = {
      name = local.platform_tools_kv.zammad
      data = [
        { key = "db-password", value = var.incident_zammad_db_password },
        { key = "admin-password", value = var.incident_zammad_admin_password },
      ]
    }
  })
}

# The blackbox exporter's Qwen check: the models URL and the key it sends.
# The URL is an address, so it is here and not in gitops/ (decision 21).
resource "kubectl_manifest" "platform_tools_qwen_kv" {
  provider = kubectl.platform_tools

  validate_schema  = false
  sensitive_fields = ["spec.data"]
  ignore_fields    = ["spec.data"]
  yaml_body = yamlencode({
    apiVersion = "secretstore.vmware.com/v1alpha1"
    kind       = "KeyValueSecret"
    metadata = {
      name      = local.platform_tools_kv.qwen
      namespace = local.namespace_names["platform-tools"]
    }
    spec = {
      name = local.platform_tools_kv.qwen
      data = [
        { key = "base-url", value = var.music_store_chat.base_url },
        { key = "api-key", value = var.incident_qwen_api_key },
      ]
    }
  })
}
