output "security_policy_path" {
  description = "NSX path of the music store's parent security policy."
  value       = nsxt_policy_parent_security_policy.music_store.path
}

output "container_cluster_path" {
  description = "NSX path of the VKS cluster music-store as an Antrea container cluster."
  value       = local.music_store_cluster_path
}

output "group_paths" {
  description = "NSX paths of the shop's service groups, by service."
  value       = { for name, group in nsxt_policy_group.music_store_service : name => group.path }
}
