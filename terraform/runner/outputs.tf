output "namespace" {
  description = "The runner's Supervisor Namespace."
  value       = vsphere_namespace.runner.name
}

output "runner_enabled" {
  description = "False until github_app_id is set: the namespace exists, and no runner."
  value       = local.runner_enabled
}
