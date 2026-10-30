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
      source = merge({
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/${each.key}"
      }, contains(keys(local.gitops_patches), each.key) ? { kustomize = { patches = local.gitops_patches[each.key] } } : {})
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

# --- The music store's handoff ---
#
# The platform engineer deploys the music store; the developer only
# writes its code in gitops/music-store-apps/src (decision 45). The
# Application music-store syncs the Supervisor Namespace's part: the
# cluster, the catalog and the users VM. Two more Applications go into
# the VKS cluster:
#
#   music-store-platform  gitops/music-store-platform: the ESO store, the
#                         Gateway certificate, the platform tools' agent.
#   music-store-apps      gitops/music-store-apps, into the namespace
#                         music-store: the shop's containers.
#
# The cluster name comes from its file, and Terraform registers that
# cluster with Argo CD. On a first build the cluster does not exist yet
# when this applies: the ManagedEntity waits for it, and both
# Applications retry until what they need is there.

locals {
  music_store_cluster_name = yamldecode(file("${path.module}/../../gitops/music-store/cluster.yaml")).metadata.name
  music_store_namespace    = local.namespace_names["music-store"]
  music_store_kv_path      = { for k, name in local.music_store_kv : k => "secret/data/${local.music_store_namespace}/${name}" }

  # The generated Supervisor Namespace name, patched over the placeholder
  # SUPERVISOR_NAMESPACE in the manifests that need it for Secret Store
  # (decision 38). Keyed by Application name.
  gitops_patches = {
    "music-store" = [{
      target = { kind = "Job", name = "catalog-init" }
      patch = yamlencode({
        apiVersion = "batch/v1"
        kind       = "Job"
        metadata   = { name = "catalog-init" }
        spec = { template = { metadata = { annotations = {
          "vault.hashicorp.com/role"                          = local.music_store_namespace
          "vault.hashicorp.com/agent-inject-secret-catalog"   = local.music_store_kv_path.catalog
          "vault.hashicorp.com/agent-inject-template-catalog" = "{{ with secret \"${local.music_store_kv_path.catalog}\" }}{{ .Data.data.password }}{{ end }}"
        } } } }
      })
    }]
    "music-store-platform" = [{
      target = { kind = "ClusterSecretStore", name = "secret-store" }
      patch = yamlencode({
        apiVersion = "external-secrets.io/v1"
        kind       = "ClusterSecretStore"
        metadata   = { name = "secret-store" }
        spec = { provider = { vault = { auth = { kubernetes = {
          mountPath = "kubernetes-${local.music_store_namespace}-${local.music_store_cluster_name}"
          role      = "${local.music_store_namespace}-${local.music_store_cluster_name}"
        } } } } }
      })
    }]
    "music-store-apps" = [for name, kv in { "store-db" = "catalog", "metal-oracle-model" = "chat" } : {
      target = { kind = "ExternalSecret", name = name }
      patch = yamlencode({
        apiVersion = "external-secrets.io/v1"
        kind       = "ExternalSecret"
        metadata   = { name = name }
        spec       = { dataFrom = [{ extract = { key = "${local.music_store_namespace}/${local.music_store_kv[kv]}" } }] }
      })
    }]
  }

  retry_sync_policy = {
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

resource "kubectl_manifest" "music_store_apps_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "music-store-apps", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/music-store-apps"
        kustomize      = { patches = local.gitops_patches["music-store-apps"] }
      }
      destination = { name = "music-store-cluster", namespace = "music-store" }
      # The namespace inside the VKS cluster is not a Supervisor Namespace,
      # and nothing else creates it.
      syncPolicy = merge(local.retry_sync_policy, { syncOptions = ["CreateNamespace=true"] })
    }
  })

  depends_on = [kubectl_manifest.music_store_cluster_entity]
}

# Renamed from music-store-dev-app (decision 45). The Application has no
# finalizer, so replacing it leaves the shop running, and the new
# Application takes the resources over by their tracking annotation.
moved {
  from = kubectl_manifest.music_store_dev_app_application
  to   = kubectl_manifest.music_store_apps_application
}

# The platform engineer's part inside the VKS cluster: the ClusterSecretStore
# that ESO reads Secret Store with (decision 38). ESO itself is the addon
# in gitops/music-store, so this retries until its CRDs exist.
resource "kubectl_manifest" "music_store_platform_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "music-store-platform", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/music-store-platform"
        kustomize      = { patches = local.gitops_patches["music-store-platform"] }
      }
      destination = { name = "music-store-cluster", namespace = "secret-store" }
      syncPolicy  = merge(local.retry_sync_policy, { syncOptions = ["CreateNamespace=true"] })
    }
  })

  depends_on = [kubectl_manifest.music_store_cluster_entity]
}

# --- The platform tools cluster (decision 42) ---
#
# The generic Application platform-tools syncs gitops/platform-tools into
# its Supervisor Namespace: the VKS cluster and its ESO addon. This one
# syncs gitops/platform-tools-apps into the cluster: Secret Store's
# ClusterSecretStore, Zammad, Grafana, Prometheus and the blackbox
# exporter. Both are the platform engineer's.

locals {
  platform_tools_cluster_name = yamldecode(file("${path.module}/../../gitops/platform-tools/cluster.yaml")).metadata.name
  platform_tools_namespace    = local.namespace_names["platform-tools"]

  platform_tools_patches = concat(
    [{
      target = { kind = "ClusterSecretStore", name = "secret-store" }
      patch = yamlencode({
        apiVersion = "external-secrets.io/v1"
        kind       = "ClusterSecretStore"
        metadata   = { name = "secret-store" }
        spec = { provider = { vault = { auth = { kubernetes = {
          mountPath = "kubernetes-${local.platform_tools_namespace}-${local.platform_tools_cluster_name}"
          role      = "${local.platform_tools_namespace}-${local.platform_tools_cluster_name}"
        } } } } }
      })
    }],
    [for name, kv in { "grafana-admin" = "grafana", "zammad-env" = "zammad", "qwen-probe" = "qwen" } : {
      target                           = { kind = "ExternalSecret", name = name }
      patch = yamlencode({
        apiVersion = "external-secrets.io/v1"
        kind       = "ExternalSecret"
        metadata   = { name = name }
        spec       = { dataFrom = [{ extract = { key = "${local.platform_tools_namespace}/${local.platform_tools_kv[kv]}" } }] }
      })
    }],
  )
}

resource "kubectl_manifest" "platform_tools_cluster_entity" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argocd-service.vsphere.vmware.com/v1alpha1"
    kind       = "ManagedEntity"
    metadata   = { name = "platform-tools-cluster", namespace = local.platform_namespace }
    spec = {
      clusterName = "platform-tools-cluster"
      targetRef = {
        apiGroup  = "cluster.x-k8s.io"
        kind      = "Cluster"
        name      = local.platform_tools_cluster_name
        namespace = local.platform_tools_namespace
        project   = var.project_name
      }
    }
  })

  depends_on = [terracurl_request.argocd_service_account_role]
}

resource "kubectl_manifest" "platform_tools_apps_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "platform-tools-apps", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/platform-tools-apps"
        kustomize      = { patches = local.platform_tools_patches }
      }
      destination = { name = "platform-tools-cluster", namespace = "incident-tools" }
      syncPolicy  = merge(local.retry_sync_policy, { syncOptions = ["CreateNamespace=true"] })
    }
  })

  depends_on = [kubectl_manifest.platform_tools_cluster_entity]
}

# The music store's image builds (decision 48): Tekton's TektonConfig, the
# Pipeline and its Tasks, and the login the workflow
# music-store-images.yml starts them with, in the namespace
# music-store-builds of the platform tools cluster. BuildKit needs a
# privileged container, so the namespace is Pod Security privileged.

locals {
  platform_tools_builds_patches = [for name, kv in { "harbor-push" = "harbor_push", "git-deploy-key" = "git_deploy_key" } : {
    target = { kind = "ExternalSecret", name = name }
    patch = yamlencode({
      apiVersion = "external-secrets.io/v1"
      kind       = "ExternalSecret"
      metadata   = { name = name }
      spec       = { dataFrom = [{ extract = { key = "${local.platform_tools_namespace}/${local.platform_tools_kv[kv]}" } }] }
    })
  }]
}

resource "kubectl_manifest" "platform_tools_builds_application" {
  provider = kubectl.platform

  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata   = { name = "platform-tools-builds", namespace = local.platform_namespace }
    spec = {
      project = "default"
      source = {
        repoURL        = var.gitops_repo.url
        targetRevision = var.gitops_repo.revision
        path           = "gitops/platform-tools-builds"
        kustomize      = { patches = local.platform_tools_builds_patches }
      }
      destination = { name = "platform-tools-cluster", namespace = "music-store-builds" }
      syncPolicy = merge(local.retry_sync_policy, {
        syncOptions = ["CreateNamespace=true"]
        managedNamespaceMetadata = {
          labels = {
            "pod-security.kubernetes.io/enforce" = "privileged"
            "pod-security.kubernetes.io/warn"    = "privileged"
          }
        }
      })
    }
  })

  depends_on = [kubectl_manifest.platform_tools_cluster_entity]
}
