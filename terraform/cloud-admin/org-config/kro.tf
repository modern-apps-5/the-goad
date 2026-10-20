# The org's kro author project. Editors and admins of a project listed in
# the kro Supervisor Service's multitenancy.orgs[].authorProjects may
# create ResourceGraphDefinitions in the API group goad.kro.run. The
# service matches the project by its uid, so any name works.
#
# The platform engineer group gets the role edit in it (users.tf). The automation
# user is an Organization Administrator, so it already counts as an
# editor, and Argo CD reaches the Supervisor as that user.
#
# Authors need a namespace of the project for their kubectl context, so
# this root makes one small namespace. Instances of goad.kro.run kinds go
# in the org's other namespaces.
#
# The service itself, and the project's uid in its values, are set by the
# vSphere admin on the Supervisor: see decision 35.

resource "kubectl_manifest" "kro_authors_project" {
  provider = kubectl.org

  # A client-side apply sets the last-applied annotation after create, and
  # the API refuses it: "Only project spec can be updated".
  server_side_apply = true
  validate_schema   = false
  yaml_body = yamlencode({
    apiVersion = "project.cci.vmware.com/v1alpha2"
    kind       = "Project"
    metadata   = { name = var.kro_authors_project }
    spec = {
      description = "kro author project: its editors publish ResourceGraphDefinitions in goad.kro.run. Managed by terraform/cloud-admin/org-config."
    }
  })
}

resource "vcfa_supervisor_namespace" "kro_authors" {
  name_prefix  = "kro-authors"
  description  = "kro authors' context. Managed by terraform/cloud-admin/org-config."
  project_name = kubectl_manifest.kro_authors_project.name
  region_name  = var.region_name
  vpc_name     = var.vpc_name
  class_name   = "small"
  seg_name     = var.service_engine_group_name

  # Only for the kubectl context. RGDs are cluster-scoped and use no quota.
  storage_classes_class_config_overrides {
    name  = var.storage_class_name
    limit = "10Gi"
  }

  zones_class_config_overrides {
    name               = var.zone_name
    cpu_limit          = "2000M"
    cpu_reservation    = "0M"
    memory_limit       = "4Gi"
    memory_reservation = "0Mi"
  }

  depends_on = [time_sleep.service_engine_group]
}

# Read the generated name through a local value: see decision 23.
locals {
  kro_authors_namespace = vcfa_supervisor_namespace.kro_authors.name
}
