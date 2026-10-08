# The contract with the platform engineer. Their Terraform and Argo CD
# need the org to log in to and the region to place namespaces in.

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

output "org_admin_username" {
  value = vcfa_org_local_user.admin.username
}
