# The contract with terraform/cloud-admin/org-config and the platform
# engineer.

output "org_name" {
  value = vcfa_org.this.name
}

output "org_id" {
  value = vcfa_org.this.id
}

output "region_name" {
  value = data.vcfa_region.this.name
}

output "region_id" {
  value = data.vcfa_region.this.id
}

output "zone_names" {
  value = keys(var.zone_allocations)
}

output "vm_class_names" {
  value = var.vm_class_names
}

output "storage_policy_names" {
  value = keys(var.storage_policy_limits_mib)
}

output "cloud_admin_username" {
  value = vcfa_org_local_user.cloud_admin.username
}
