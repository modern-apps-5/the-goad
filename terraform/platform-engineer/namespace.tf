# The org already has a default project and a default VPC for the region.
# This demo uses them and does not create its own.
#
# Terraform creates the Supervisor Namespaces. Argo CD runs in "platform"
# and deploys into the others.
resource "vcfa_supervisor_namespace" "namespaces" {
  for_each = var.namespaces

  name_prefix  = each.key
  description  = each.value.description
  project_name = var.project_name
  region_name  = var.region_name
  vpc_name     = var.vpc_name
  class_name   = each.value.class_name
  seg_name     = var.service_engine_group_name

  storage_classes_class_config_overrides {
    name  = var.storage_class_name
    limit = each.value.storage_limit
  }

  zones_class_config_overrides {
    name               = var.zone_name
    cpu_limit          = each.value.cpu_limit
    cpu_reservation    = each.value.cpu_reservation
    memory_limit       = each.value.memory_limit
    memory_reservation = each.value.memory_reservation
  }

  depends_on = [time_sleep.service_engine_group]
}

# The generated names, by key. Everything else in this root reads names
# from here, not from the resource above.
#
# That is on purpose. Terraform looks up the address of a namespace's
# Kubernetes API with a data source. A data source that refers straight to
# a resource is not read until apply when that resource has any pending
# change, and adding or resizing a namespace is one. With no address,
# every existing Kubernetes object then fails to refresh:
#
#   Get "http://localhost/api": dial tcp 127.0.0.1:80: connection refused
#
# Going through this local value avoids that. The names themselves are
# already known, so the lookups are read at plan time.
locals {
  namespace_names = { for key, namespace in vcfa_supervisor_namespace.namespaces : key => namespace.name }
}
