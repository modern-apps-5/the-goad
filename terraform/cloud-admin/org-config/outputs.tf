# The contract with terraform/cloud-admin/agentminder, which reads this
# root's state, and the kro author project's names.

output "cloud_admin_project" {
  value = kubectl_manifest.cloud_admin_project.name
}

output "agentminder_namespace" {
  value = local.agentminder_namespace
}

output "agentminder_cluster_name" {
  value = vcfa_vks_cluster.agentminder.name
}

output "kro_authors_project" {
  value = kubectl_manifest.kro_authors_project.name
}

output "kro_authors_namespace" {
  value = local.kro_authors_namespace
}
