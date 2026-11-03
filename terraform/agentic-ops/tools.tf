# The agents' tool wiring: the sc-* user-provided services in the space the
# platform engineer owns. The manifest
# (tanzu/metal-music-app-agentic-system/manifest.yml) binds each one to its
# agent. They were the platform engineer's first, in terraform/platform-engineer/
# tanzu.tf. That root has a removed block for each, with destroy = false, so
# either root can apply first and nothing is deleted.
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

# The services were made by hand before any root owned them. Remove these
# blocks once they are in every state.
import {
  to = cloudfoundry_service_instance.orchestrator_tools
  id = "a0881d91-d59f-4775-a538-6218233a6dc3"
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

import {
  to = cloudfoundry_service_instance.sidecar_tools["sc-lb-diagnostic-agent-avi"]
  id = "21b30a57-1dd6-4ec3-924f-47d7c3693bb0"
}

import {
  to = cloudfoundry_service_instance.sidecar_tools["sc-k8s-diagnostic-agent-k8s"]
  id = "52c99ec9-9cc6-49d0-9ce3-7d3e7d99724a"
}

import {
  to = cloudfoundry_service_instance.sidecar_tools["sc-vcf-diagnostic-agent-vcf"]
  id = "4d81c9a6-3248-4de8-b07a-e3a5f4405247"
}
