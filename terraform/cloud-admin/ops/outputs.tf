output "dashboards" {
  description = "Imported platform observability dashboards: file name to VCF Operations dashboard ID."
  value       = { for name, import in terracurl_request.dashboard : name => jsondecode(import.response).data.dashboard_id }
}

output "vks_node_disk_latency_alert_id" {
  description = "The alert definition for a VKS node VM with a slow virtual disk."
  value       = jsondecode(terracurl_request.vks_node_disk_latency_alert.response).id
}
