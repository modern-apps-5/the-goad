data "vcfa_region_zone" "this" {
  for_each  = var.zone_allocations
  region_id = data.vcfa_region.this.id
  name      = each.key
}

data "vcfa_region_vm_class" "this" {
  for_each  = var.vm_class_names
  region_id = data.vcfa_region.this.id
  name      = each.key
}

data "vcfa_region_storage_policy" "this" {
  for_each  = var.storage_policy_limits_mib
  region_id = data.vcfa_region.this.id
  name      = each.key
}

# The quota is the ceiling for every Supervisor Namespace the platform
# engineer creates in this org. A GPU VM class listed in var.vm_class_names
# is how the tenant gets GPU capacity.
resource "vcfa_org_region_quota" "this" {
  org_id         = vcfa_org.this.id
  region_id      = data.vcfa_region.this.id
  supervisor_ids = data.vcfa_region.this.supervisor_ids

  dynamic "zone_resource_allocations" {
    for_each = var.zone_allocations
    content {
      region_zone_id         = data.vcfa_region_zone.this[zone_resource_allocations.key].id
      cpu_limit_mhz          = zone_resource_allocations.value.cpu_limit_mhz
      cpu_reservation_mhz    = zone_resource_allocations.value.cpu_reservation_mhz
      memory_limit_mib       = zone_resource_allocations.value.memory_limit_mib
      memory_reservation_mib = zone_resource_allocations.value.memory_reservation_mib
    }
  }

  region_vm_class_ids = [for class in data.vcfa_region_vm_class.this : class.id]

  dynamic "region_storage_policy" {
    for_each = var.storage_policy_limits_mib
    content {
      region_storage_policy_id = data.vcfa_region_storage_policy.this[region_storage_policy.key].id
      storage_limit_mib        = region_storage_policy.value
    }
  }
}
