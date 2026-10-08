resource "vcfa_org_networking" "this" {
  org_id   = vcfa_org.this.id
  log_name = var.org_log_name
}

# The rest of this file connects the org to the region's Distributed VLAN
# Connection. The org's VPCs get their external addresses from the IP space
# on that connection.
#
# vcfa_org_regional_networking (provider 1.2.x) only accepts a provider
# gateway, and this region has none. TerraCurl calls the same API with the
# connection. Replace these resources with vcfa_org_regional_networking when
# the provider supports the connection.

# The virtual network appliance cluster that runs the org's VPC services.
# The vcfa provider has no data source for it.
data "terracurl_request" "vna_cluster" {
  name               = "vna-cluster"
  method             = "GET"
  url                = "${local.vcfa_api}/vcf/virtualNetworkApplianceClusters"
  request_parameters = { filter = "name==${var.vna_cluster_name}" }
  response_codes     = ["200"]
  skip_tls_verify    = var.allow_unverified_ssl

  lifecycle {
    postcondition {
      condition = length([
        for cluster in jsondecode(self.response).values : cluster
        if cluster.regionRef.id == data.vcfa_region.this.id
      ]) == 1
      error_message = "Region ${var.region_name} has no virtual network appliance cluster named ${var.vna_cluster_name}."
    }
  }
}

locals {
  vna_cluster_id = one([
    for cluster in jsondecode(data.terracurl_request.vna_cluster.response).values : cluster.id
    if cluster.regionRef.id == data.vcfa_region.this.id
  ])
}

# The create call. VCF Automation answers before the setting is realized,
# and the answer does not hold the new ID, so this resource cannot delete
# what it creates. The resource at the end of the file does.
resource "terracurl_request" "org_regional_networking_create" {
  name    = "org-regional-networking-create"
  method  = "POST"
  url     = "${local.vcfa_api}/vcf/regionalNetworkingSettings"
  headers = { "Content-Type" = "application/json" }
  request_body = jsonencode({
    name = "${var.org_name}${var.region_name}"
    # Reference vcfa_org_networking, not vcfa_org, so the org networking
    # settings exist first.
    orgRef                            = { id = vcfa_org_networking.this.id }
    regionRef                         = { id = data.vcfa_region.this.id }
    distributedVlanConnectionRef      = { id = data.vcfa_distributed_vlan_connection.this.id }
    virtualNetworkApplianceClusterRef = { id = local.vna_cluster_id }
  })
  response_codes  = ["200", "201", "202"]
  skip_tls_verify = var.allow_unverified_ssl
  skip_destroy    = true

  # VCF Automation refuses to delete the quota while the regional networking
  # setting exists. This makes destroy remove the setting first.
  depends_on = [vcfa_org_region_quota.this]
}

# Time for the new setting to show up in the list after create, and for
# VCF Automation to remove it after delete and before the quota goes.
resource "time_sleep" "org_regional_networking" {
  create_duration  = "10s"
  destroy_duration = "30s"

  depends_on = [terracurl_request.org_regional_networking_create]
}

locals {
  org_regional_networking_filter = "orgRef.id==${vcfa_org_networking.this.id};regionRef.id==${data.vcfa_region.this.id}"
}

# Reads the new setting, and deletes it on destroy. The ID in the destroy
# URL comes from the stored read response.
#
# This does not wait for the setting to be realized. That takes from a few
# seconds to a few minutes, and TerraCurl can only retry on a status code.
# The check block below reports the status.
resource "terracurl_request" "org_regional_networking" {
  name               = "org-regional-networking"
  method             = "GET"
  url                = "${local.vcfa_api}/vcf/regionalNetworkingSettings"
  request_parameters = { filter = local.org_regional_networking_filter }
  response_codes     = ["200"]
  skip_tls_verify    = var.allow_unverified_ssl

  # skip_destroy defaults to true. Without this line destroy sends nothing.
  skip_destroy            = false
  destroy_url             = "${local.vcfa_api}/vcf/regionalNetworkingSettings/{response.values.0.id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["200", "202", "204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl

  depends_on = [time_sleep.org_regional_networking]
}

# A warning, not an error: the org exists, but Supervisor Namespaces cannot
# be created in it until the setting is realized.
check "org_regional_networking_realized" {
  data "terracurl_request" "org_regional_networking_status" {
    name               = "org-regional-networking-status"
    method             = "GET"
    url                = "${local.vcfa_api}/vcf/regionalNetworkingSettings"
    request_parameters = { filter = local.org_regional_networking_filter }
    response_codes     = ["200"]
    skip_tls_verify    = var.allow_unverified_ssl

    depends_on = [terracurl_request.org_regional_networking]
  }

  assert {
    condition     = try(jsondecode(data.terracurl_request.org_regional_networking_status.response).values[0].status, "") == "REALIZED"
    error_message = "Regional networking for org ${var.org_name} is not realized yet. Run terraform plan again in a minute to check."
  }
}

# Turns on the Avi load balancer for the org in this region. Until this is
# set, the org cannot create a Service Engine Group, and a Supervisor
# Namespace that names one is refused.
#
# TENANT_MANAGED: the org creates and sizes its own Service Engine Groups,
# up to the quota. The platform engineer does that.
#
# The setting hangs off the regional networking setting, which may still be
# configuring. The retries wait for it.
resource "terracurl_request" "org_avi_setting" {
  count = var.avi_service_engine_group_quota == 0 ? 0 : 1

  name    = "org-avi-setting"
  method  = "PUT"
  url     = "${local.vcfa_api}/vcf/regionalNetworkingSettings/${jsondecode(terracurl_request.org_regional_networking.response).values[0].id}/aviSetting"
  headers = { "Content-Type" = "application/json" }
  request_body = jsonencode({
    active                 = true
    serviceEngineGroupMode = "TENANT_MANAGED"
    serviceEngineQuota     = var.avi_service_engine_group_quota
  })
  response_codes  = ["200", "201", "202"]
  max_retry       = 20
  retry_interval  = 15
  skip_tls_verify = var.allow_unverified_ssl

  # Nothing to send on destroy: the setting goes with the regional
  # networking setting.
  skip_destroy = true
}
