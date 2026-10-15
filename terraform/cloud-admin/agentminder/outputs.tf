data "kubernetes_service_v1" "ingress_nginx" {
  metadata {
    name      = "ingress-nginx-controller"
    namespace = helm_release.ingress_nginx.namespace
  }
}

# The address agentminder_hostname must resolve to.
output "ingress_address" {
  value = try(data.kubernetes_service_v1.ingress_nginx.status[0].load_balancer[0].ingress[0].ip, null)
}

output "agentminder_url" {
  value = "https://${var.agentminder_hostname}"
}
