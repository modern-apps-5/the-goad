# Addons the lab's Supervisor offers that VKS does not ship: kagent, from
# warroyo/vks-kagent-addon (decision 56). Registering an AddonRepository in
# vmware-system-vks-public takes a Supervisor administrator, and this root
# is the only one that logs in as one. Platform engineers then install the
# addon on their clusters with an AddonInstall (gitops/agents/kagent.yaml).
#
# Once the AddonRepositoryInstall exists, the webhook lets only
# spec.addonFilters change. To offer a new chart version, add it to
# kagent_addon_versions, and keep the old one while a cluster still uses it.
# The package-offerings annotation cannot change after install, so it lists
# no versions.

resource "kubectl_manifest" "kagent_addon_repository" {
  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "addons.kubernetes.vmware.com/v1alpha1"
    kind       = "AddonRepository"
    metadata = {
      name      = "kagent-oci-repo"
      namespace = "vmware-system-vks-public"
      annotations = {
        "addons.kubernetes.vmware.com/package-offerings" = jsonencode({
          repositoryVersion = "1.0.0"
          packages          = { kagent = { versions = [] } }
        })
      }
    }
    spec = {
      fetch                = { helmRepository = { url = "oci://ghcr.io/warroyo/vks-kagent-addon/charts" } }
      addonFilters         = [{ name = "kagent", versions = var.kagent_addon_versions }]
      targetRepositoryName = "kagent-oci-repo"
      version              = "1.0.0"
    }
  })
}

resource "kubectl_manifest" "kagent_addon_repository_install" {
  validate_schema = false
  yaml_body = yamlencode({
    apiVersion = "addons.kubernetes.vmware.com/v1alpha1"
    kind       = "AddonRepositoryInstall"
    metadata   = { name = "kagent-oci-repo-install", namespace = "vmware-system-vks-public" }
    spec = {
      addonRepositoryRef = { name = "kagent-oci-repo", namespace = "vmware-system-vks-public" }
    }
  })

  depends_on = [kubectl_manifest.kagent_addon_repository]
}
