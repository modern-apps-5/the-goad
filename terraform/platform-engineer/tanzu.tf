# The incident apps' place on Tanzu Platform: org Goad, foundation goad.
#
# This root owns the space and the user-provided services in it. The apps
# themselves are pushed by .github/workflows/tanzu-apps.yml from
# tanzu/metal-music-app-agentic-system, which binds these services by name.
# The org exists already and is not this root's: it is only read.
#
# The provider logs in with an access token, CF_ACCESS_TOKEN, that the
# cf-token action gets as goad-deployer. The foundation takes only that
# app's client assertion secret, and the provider cannot sign one. On a
# machine: CF_ACCESS_TOKEN=$(~/.claude/skills/lab-creds/cf-token.py).
provider "cloudfoundry" {
  api_url             = var.cf_api_url
  skip_ssl_validation = var.allow_unverified_ssl
}

locals {
  # The agents reach the model through a proxy on 127.0.0.1:8765 in their
  # own container (tanzu/.../shared/trust), so the binding names that.
  goad_qwen_proxy = "http://127.0.0.1:8765/api/v1/compatibility"
  # The diagnostic agents' MCP tools: the AgentMinder sidecar in the same
  # container, one resource for each agent.
  sidecar_tools = {
    "sc-lb-diagnostic-agent-avi"  = "avi"
    "sc-k8s-diagnostic-agent-k8s" = "k8s"
    "sc-vcf-diagnostic-agent-vcf" = "vcf"
  }
}

data "cloudfoundry_org" "goad" {
  name = var.cf_org_name
}

resource "cloudfoundry_space" "agentic" {
  name = "metal-music-app-agentic-system"
  org  = data.cloudfoundry_org.goad.id
}

# The space and the services were made by hand before this root owned them.
# Remove these blocks once they are in every state.
import {
  to = cloudfoundry_space.agentic
  id = "338a6093-3030-4c8a-b724-3a84ff831aae"
}

# The model binding that agent_buildpack reads. The api key is the Private
# AI Services key the agents use; the same key is in the apps' env.
resource "cloudfoundry_service_instance" "goad_qwen" {
  name  = "goad-qwen"
  type  = "user-provided"
  space = cloudfoundry_space.agentic.id
  tags  = ["tanzu-ai-models", "ai-models", "genai", "llm"]
  credentials = jsonencode({
    api_base           = "${local.goad_qwen_proxy}/openai/v1"
    api_key            = var.incident_qwen_api_key
    model_name         = "qwen"
    model_capabilities = ["chat", "tools"]
    wire_format        = "openai"
    endpoint = {
      api_base        = local.goad_qwen_proxy
      openai_api_base = "${local.goad_qwen_proxy}/openai/v1"
      api_key         = var.incident_qwen_api_key
      config_url      = "https://metal-incident-live.${var.cf_apps_domain}/config/v1/endpoint"
      name            = "qwen"
    }
  })
}

import {
  to = cloudfoundry_service_instance.goad_qwen
  id = "a8cf043b-dfe0-4c81-8e19-13bd0c965693"
}

# metal-k8s-mcp's view of the music store cluster.
resource "cloudfoundry_service_instance" "k8s_mcp_cluster" {
  name  = "k8s-mcp-cluster"
  type  = "user-provided"
  space = cloudfoundry_space.agentic.id
  credentials = jsonencode({
    server    = var.incident_k8s_api_server
    token     = var.incident_k8s_token
    namespace = "metal-music-store"
  })
}

import {
  to = cloudfoundry_service_instance.k8s_mcp_cluster
  id = "7578c44a-b628-4571-aa87-b1d1b9d381e8"
}

# The incident response agent's one tool: the orchestrator, on the
# container network.
resource "cloudfoundry_service_instance" "orchestrator_tools" {
  name  = "sc-incident-response-agent-orch"
  type  = "user-provided"
  space = cloudfoundry_space.agentic.id
  tags  = ["mcp-server"]
  credentials = jsonencode({
    url = "http://metal-incident-live.apps.internal:8080/mcp"
  })
}

import {
  to = cloudfoundry_service_instance.orchestrator_tools
  id = "a0881d91-d59f-4775-a538-6218233a6dc3"
}

resource "cloudfoundry_service_instance" "sidecar_tools" {
  for_each = local.sidecar_tools

  name  = each.key
  type  = "user-provided"
  space = cloudfoundry_space.agentic.id
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
