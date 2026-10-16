# The org's Avi Service Engine Group. Every load balancer in the org's
# namespaces runs on these Service Engines, the cloud admin's and the
# platform engineer's.
#
# The cloud admin set the org to manage its own groups, within a quota
# (terraform/cloud-admin/org). This root creates the group because its own
# AgentMinder namespace needs it, and this root runs before
# terraform/platform-engineer. Sized small: two 1-vCPU, 2 GB Service
# Engines shared by all virtual services.
#
# A SEG is an object in the org's Kubernetes API. That API does not publish
# an OpenAPI schema for it, so kubernetes_manifest cannot plan it ("resource
# not found in OpenAPI index"). The kubectl provider does not need the
# schema.
resource "kubectl_manifest" "service_engine_group" {
  provider        = kubectl.org
  validate_schema = false

  yaml_body = yamlencode({
    apiVersion = "avi.vmware.com/v1alpha1"
    kind       = "SEG"
    metadata = {
      name = var.service_engine_group_name
    }
    spec = {
      region                  = var.region_name
      zones                   = [var.zone_name]
      haMode                  = "HA_MODE_SHARED"
      numberOfvCPUsPerSE      = 1
      memoryPerSE             = 2048
      diskPerSE               = 15
      maxVSPerSE              = 30
      minScaleoutPerVS        = 2
      maxScaleoutPerVS        = 4
      enableCPUReserve        = false
      enableMemoryReserve     = false
      enableCPUSocketAffinity = false
      useHyperthreadedCores   = true
    }
  })
}

# Time for Avi to program the new group before a namespace names it.
#
# kubectl_manifest has wait_for, but it waits with a watch, and VCF
# Automation does not let an organization administrator watch SEGs.
resource "time_sleep" "service_engine_group" {
  create_duration = "20s"

  depends_on = [kubectl_manifest.service_engine_group]
}
