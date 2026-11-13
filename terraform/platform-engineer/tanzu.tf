# The incident apps' place on Tanzu Platform: org Goad, foundation goad.
#
# This root owns the space, the model binding goad-qwen, and the cluster
# service k8s-mcp-cluster. The agents' tool services (am-* and sc-*) are the
# agentic ops engineer's, in terraform/agentic-ops. The apps themselves are
# pushed by .github/workflows/tanzu-apps.yml from
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
  # The model by its name. The agents trust its certificate's CA, the GOAD
  # CA, through SSL_CERT_FILE (tanzu/.../shared/trust).
  goad_qwen_api = "https://pais.goad.gpu.set.lab/api/v1/compatibility"
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
    api_base           = "${local.goad_qwen_api}/openai/v1"
    api_key            = var.incident_qwen_api_key
    model_name         = "qwen"
    model_capabilities = ["chat", "tools"]
    wire_format        = "openai"
    endpoint = {
      api_base        = local.goad_qwen_api
      openai_api_base = "${local.goad_qwen_api}/openai/v1"
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
