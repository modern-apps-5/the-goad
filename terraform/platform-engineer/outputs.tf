output "namespaces" {
  description = "Generated Supervisor Namespace names, keyed by name prefix."
  value       = { for key, namespace in vcfa_supervisor_namespace.namespaces : key => namespace.name }
}
