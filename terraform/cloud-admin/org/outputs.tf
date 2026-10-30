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

output "music_store_registry" {
  description = "Where the platform engineer pushes the music store's images, and the robot account to push with. The secret is the GitHub secret MUSIC_STORE_HARBOR_ROBOT_SECRET."
  value = {
    repository = "${trimprefix(var.harbor_url, "https://")}/${harbor_project.music_store.name}"
    username   = harbor_robot_account.music_store_builder.full_name
  }
}
