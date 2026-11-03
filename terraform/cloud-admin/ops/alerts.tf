# --- Alert: a VKS node VM with a slow virtual disk ---
#
# Fires on a VKS node VM (a VM with a KubernetesNode child, not every VM in
# the lab) when one of its virtual disks has write latency over
# node_disk_latency_threshold_ms for one collection (five minutes). The
# symptom names the disk, so a slow PVC disk shows apart from the node's OS
# disk. VCF Operations' own VM latency symptoms wait three collections and
# raise no alert by themselves. The VKS cluster shows this alert with its
# descendants included.
#
# A new alert definition is deactivated in Base Settings, so every policy
# inherits it off. vks_node_disk_latency_enabled turns it on in the default
# policy. A policy assigned to the cluster's objects instead needs it
# turned on there.
#
# There is no read call here, so a definition changed in the UI is not
# seen. A changed body makes a new definition and deletes the old one.
locals {
  json_headers = { "Content-Type" = "application/json" }
}

resource "terracurl_request" "vks_node_disk_latency_symptom" {
  name    = "vks-node-disk-latency-symptom"
  method  = "POST"
  url     = "${local.ops_api}/symptomdefinitions"
  headers = local.json_headers
  request_body = jsonencode({
    name            = "VKS node virtual disk write latency high"
    adapterKindKey  = "VMWARE"
    resourceKindKey = "VirtualMachine"
    waitCycles      = 1
    cancelCycles    = 1
    state = {
      severity = "CRITICAL"
      condition = {
        type          = "CONDITION_HT"
        key           = "virtualDisk|totalWriteLatency_average"
        operator      = "GT"
        value         = tostring(var.node_disk_latency_threshold_ms)
        valueType     = "NUMERIC"
        instanced     = true
        thresholdType = "STATIC"
      }
    }
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  skip_destroy            = false
  destroy_url             = "${local.ops_api}/symptomdefinitions/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["200", "204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}

# Always true on a KubernetesNode. The alert needs it on the VM's child to
# tell a VKS node VM from any other VM.
resource "terracurl_request" "vks_node_symptom" {
  name    = "vks-node-symptom"
  method  = "POST"
  url     = "${local.ops_api}/symptomdefinitions"
  headers = local.json_headers
  request_body = jsonencode({
    name            = "VKS node is available"
    adapterKindKey  = "SupervisorAdapter"
    resourceKindKey = "KubernetesNode"
    waitCycles      = 1
    cancelCycles    = 1
    state = {
      severity = "INFORMATION"
      condition = {
        type          = "CONDITION_HT"
        key           = "System Attributes|availability"
        operator      = "GT"
        value         = "0"
        valueType     = "NUMERIC"
        instanced     = false
        thresholdType = "STATIC"
      }
    }
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  skip_destroy            = false
  destroy_url             = "${local.ops_api}/symptomdefinitions/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["200", "204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}

resource "terracurl_request" "vks_node_disk_latency_recommendation" {
  name    = "vks-node-disk-latency-recommendation"
  method  = "POST"
  url     = "${local.ops_api}/recommendations"
  headers = local.json_headers
  request_body = jsonencode({
    description = join(" ", [
      "Open the VKS node's virtual machine. In its Metrics, compare write latency per",
      "virtual disk: a PVC disk is slow while the OS disk is not. Check that disk's",
      "storage policy in the VM's properties, and its vSAN IOPS limit in vCenter,",
      "before looking at the host or the vSAN cluster.",
    ])
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  skip_destroy            = false
  destroy_url             = "${local.ops_api}/recommendations/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["200", "204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}

resource "terracurl_request" "vks_node_disk_latency_alert" {
  name    = "vks-node-disk-latency-alert"
  method  = "POST"
  url     = "${local.ops_api}/alertdefinitions"
  headers = local.json_headers
  request_body = jsonencode({
    name            = "VKS node VM has a virtual disk with high write latency"
    description     = "A virtual disk of this VKS node VM has high write latency. The symptom names the disk. Made by terraform/cloud-admin/ops in the-goad."
    adapterKindKey  = "VMWARE"
    resourceKindKey = "VirtualMachine"
    waitCycles      = 1
    cancelCycles    = 1
    type            = 18 # Storage
    subType         = 19 # Performance
    states = [{
      severity = "AUTO"
      "base-symptom-set" = {
        type     = "SYMPTOM_SET_COMPOSITE"
        operator = "AND"
        # The same shape as VCF Operations' own alerts. A related object's
        # set names its kind and fires when at least one has the symptom.
        "symptom-sets" = [
          {
            type                 = "SYMPTOM_SET"
            relation             = "SELF"
            symptomSetOperator   = "AND"
            symptomDefinitionIds = [jsondecode(terracurl_request.vks_node_disk_latency_symptom.response).id]
          },
          {
            type                 = "SYMPTOM_SET"
            relation             = "CHILD"
            adapterKindKey       = "SupervisorAdapter"
            resourceKindKey      = "KubernetesNode"
            aggregation          = "COUNT"
            populationOperator   = "GT"
            value                = 0
            symptomSetOperator   = "AND"
            symptomDefinitionIds = [jsondecode(terracurl_request.vks_node_symptom.response).id]
          },
        ]
      }
      impact                    = { impactType = "BADGE", detail = "health" }
      recommendationPriorityMap = { (jsondecode(terracurl_request.vks_node_disk_latency_recommendation.response).id) = 1 }
    }]
  })
  response_codes  = ["200", "201"]
  skip_tls_verify = var.allow_unverified_ssl

  skip_destroy            = false
  destroy_url             = "${local.ops_api}/alertdefinitions/{response.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["200", "204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}

data "terracurl_request" "policies" {
  name            = "policies"
  method          = "GET"
  url             = "${local.ops_api}/policies"
  response_codes  = ["200"]
  skip_tls_verify = var.allow_unverified_ssl
}

locals {
  default_policy = one([for policy in jsondecode(data.terracurl_request.policies.response).policySummaries : policy if policy.defaultPolicy])
}

# Turns the alert on in the default policy. Deleting the alert takes it out
# of every policy, so there is nothing to undo on destroy.
resource "terracurl_request" "vks_node_disk_latency_enabled" {
  name               = "vks-node-disk-latency-enabled"
  method             = "PUT"
  url                = "${local.ops_api}/alertdefinitions/${jsondecode(terracurl_request.vks_node_disk_latency_alert.response).id}/enable"
  request_parameters = { policyId = local.default_policy.id }
  response_codes     = ["200", "204"]
  skip_tls_verify    = var.allow_unverified_ssl
}
