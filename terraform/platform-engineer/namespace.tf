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

moved {
  from = vcfa_supervisor_namespace.this
  to   = vcfa_supervisor_namespace.namespaces
}
