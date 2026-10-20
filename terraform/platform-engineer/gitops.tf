# The handoff to Argo CD. For each namespace other than Argo CD's own,
# Terraform registers the namespace with Argo CD and creates one
# Application that syncs gitops/<namespace key>/ into it. After that, git
# is the source for what runs in the namespace.
#
# Terraform does this, not git, because namespace names are generated
# (private-ai-xxxxx) and only Terraform knows them.

locals {
  platform_namespace = local.namespace_names["platform"]
  gitops_namespaces  = { for key, name in local.namespace_names : key => name if key != "platform" }
}

# Registers the namespace with Argo CD as a cluster named by its key.
resource "kubectl_manifest" "managed_entity" {
  for_each = local.gitops_namespaces
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argocd-service.vsphere.vmware.com/v1alpha1"
    kind       = "ManagedEntity"
    metadata   = { name = each.key, namespace = local.platform_namespace }
    spec = {
      clusterName = each.key
      targetRef   = { apiGroup = "", kind = "Namespace", name = each.value, project = var.project_name }
    }
  })

  # Argo CD cannot register a namespace before its account has the role.
  depends_on = [terracurl_request.argocd_service_account_role]
}

resource "kubectl_manifest" "application" {
  for_each = local.gitops_namespaces
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = each.key, namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/${each.key}"
      }
      destination = { name = each.key, namespace = each.value }
      syncPolicy  = { automated = { prune = true, selfHeal = true } }
    }
  })

  depends_on = [kubectl_manifest.managed_entity]
}

# Read access to the repository, with a read-only deploy key. The key
# belongs to the repository, not to a person. Needed while the repository
# is private.
resource "kubectl_manifest" "gitops_repository" {
  count    = var.gitops_repo_ssh_key_file == null ? 0 : 1
  provider = kubectl.platform

  sensitive_fields = ["stringData"]
  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Secret"
    metadata = {
      name      = "gitops-repo"
      namespace = local.platform_namespace
      labels    = { "argocd.argoproj.io/secret-type" = "repository" }
    }
    stringData = {
      type          = "git"
      url           = var.gitops_repo.url
      sshPrivateKey = file(var.gitops_repo_ssh_key_file)
    }
  })
}

# --- The developer's handoff ---
#
# The developer owns two parts of the music store, each with its own
# Application:
#
#   music-store-dev-vm   gitops/music-store-dev/users-vm, into the
#                        music-store Supervisor Namespace: the users VM.
#   music-store-dev-app  gitops/music-store-dev/app, into the namespace
#                        music-store of the VKS cluster: the containers.
#
# The platform engineer's Application music-store keeps the cluster and
# the catalog. The cluster name comes from its file, and Terraform
# registers that cluster with Argo CD. On a first build the cluster does
# not exist yet when this applies: the ManagedEntity waits for it, and
# both Applications retry until what they need is there.

locals {
  music_store_cluster_name = yamldecode(file("${path.module}/../../gitops/music-store/cluster.yaml")).metadata.name

  developer_sync_policy = {
    automated = { prune = true, selfHeal = true }
    retry     = { limit = 10, backoff = { duration = "1m", factor = 2, maxDuration = "10m" } }
  }
}

resource "kubectl_manifest" "music_store_cluster_entity" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argocd-service.vsphere.vmware.com/v1alpha1"
    kind       = "ManagedEntity"
    metadata   = { name = "music-store-cluster", namespace = local.platform_namespace }
    spec = {
      clusterName = "music-store-cluster"
      targetRef = {
        apiGroup  = "cluster.x-k8s.io"
        kind      = "Cluster"
        name      = local.music_store_cluster_name
        namespace = local.namespace_names["music-store"]
        project   = var.project_name
      }
    }
  })

  depends_on = [terracurl_request.argocd_service_account_role]
}

resource "kubectl_manifest" "music_store_dev_vm_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "music-store-dev-vm", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/music-store-dev/users-vm"
      }
      destination = { name = "music-store", namespace = local.namespace_names["music-store"] }
      syncPolicy  = local.developer_sync_policy
    }
  })

  depends_on = [kubectl_manifest.managed_entity]
}

resource "kubectl_manifest" "music_store_dev_app_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "music-store-dev-app", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/music-store-dev/app"
      }
      destination = { name = "music-store-cluster", namespace = "music-store" }
      # The namespace inside the VKS cluster is not a Supervisor Namespace,
      # and nothing else creates it.
      syncPolicy = merge(local.developer_sync_policy, { syncOptions = ["CreateNamespace=true"] })
    }
  })

  depends_on = [kubectl_manifest.music_store_cluster_entity]
}
