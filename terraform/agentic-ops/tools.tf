# The agents' tool wiring: the sc-* user-provided services in the space the
# platform engineer owns. The manifest
# (tanzu/metal-music-app-agentic-system/manifest.yml) binds each one to its
# agent. They were the platform engineer's first, in terraform/platform-engineer/
# tanzu.tf. See decision 50.
locals {
  # The diagnostic agents' MCP tools: the AgentMinder sidecar in the same
  # container, one resource for each agent.
  sidecar_tools = {
    "sc-lb-diagnostic-agent-avi"  = "avi"
    "sc-k8s-diagnostic-agent-k8s" = "k8s"
    "sc-vcf-diagnostic-agent-vcf" = "vcf"
  }
}

# The incident response agent's one tool: the orchestrator, on the
# container network.
resource "cloudfoundry_service_instance" "orchestrator_tools" {
  name  = "sc-incident-response-agent-orch"
  type  = "user-provided"
  space = data.cloudfoundry_space.agentic.id
  tags  = ["mcp-server"]
  credentials = jsonencode({
    url = "http://metal-incident-live.apps.internal:8080/mcp"
  })
}

resource "cloudfoundry_service_instance" "sidecar_tools" {
  for_each = local.sidecar_tools

  name  = each.key
  type  = "user-provided"
  space = data.cloudfoundry_space.agentic.id
  tags  = ["mcp-server"]
  credentials = jsonencode({
    url       = "http://127.0.0.1:8181/mcp?resource=${each.value}"
    api_key   = var.incident_sidecar_token
    auth_type = "bearer"
  })
}
