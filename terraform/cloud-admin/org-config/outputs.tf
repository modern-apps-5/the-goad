# The contract with terraform/cloud-admin/agentminder, which reads this
# root's state.

output "cloud_admin_project" {
  value = kubectl_manifest.cloud_admin_project.name
}

output "agentminder_namespace" {
  value = local.agentminder_namespace
}

output "agentminder_cluster_name" {
  value = vcfa_vks_cluster.agentminder.name
}
