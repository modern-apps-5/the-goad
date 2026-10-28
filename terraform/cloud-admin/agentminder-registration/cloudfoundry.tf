# The handoff to the incident apps: one user-provided service for each
# diagnostic agent, in the space the platform engineer owns, with the
# agent's AgentMinder client and its MCP server's gateway URL. The manifest
# (tanzu/metal-music-app-agentic-system/manifest.yml) binds each one to its
# agent, and the sidecar's agentminder-env.sh turns it into the variables
# the AgentMinder SDK reads. So the secrets go from AgentMinder to Cloud
# Foundry without GitHub, and tanzu-apps.yml never has them. See decision 41.
#
# A changed secret reaches an app when it restarts: cf restart <app>.
#
# The provider logs in with an access token, CF_ACCESS_TOKEN, that the
# cf-token action gets as goad-deployer, as in terraform/platform-engineer.
# On a machine: CF_ACCESS_TOKEN=$(~/.claude/skills/lab-creds/cf-token.py).
provider "cloudfoundry" {
  api_url             = var.cf_api_url
  skip_ssl_validation = var.insecure_skip_tls_verify
}

data "cloudfoundry_org" "goad" {
  name = var.cf_org_name
}

data "cloudfoundry_space" "agentic" {
  name = var.cf_space_name
  org  = data.cloudfoundry_org.goad.id
}

locals {
  # The app each diagnostic client belongs to. The service is am-<app>.
  client_apps = {
    lb  = "lb-diagnostic-agent"
    k8s = "k8s-diagnostic-agent"
    vcf = "vcf-diagnostic-agent"
  }
}

resource "cloudfoundry_service_instance" "agentminder_client" {
  for_each = local.diagnostic_clients

  name  = "am-${local.client_apps[each.key]}"
  type  = "user-provided"
  space = data.cloudfoundry_space.agentic.id
  # agentminder-env.sh finds the service by this tag.
  tags = ["agentminder-client"]
  credentials = jsonencode({
    client_id     = restapi_object.client[each.key].api_data["clientId"]
    client_secret = restapi_object.client[each.key].api_data["secret"]
    gateway_url   = local.gateway_urls[each.value.server]
  })
}
