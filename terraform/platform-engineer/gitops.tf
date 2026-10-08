# The handoff to Argo CD. For each namespace other than Argo CD's own,
# Terraform registers the namespace with Argo CD and creates one
# Application that syncs gitops/<namespace key>/ into it. After that, git
# is the source for what runs in the namespace.
#
# Terraform does this, not git, because namespace names are generated
# (private-ai-xxxxx) and only Terraform knows them.

locals {
  platform_namespace = vcfa_supervisor_namespace.namespaces["platform"].name
  gitops_namespaces  = { for key, namespace in vcfa_supervisor_namespace.namespaces : key => namespace.name if key != "platform" }
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
