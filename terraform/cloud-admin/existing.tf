# The region and its external connection are already in VCF Automation.
# This root reads them. It does not create or change them.

data "vcfa_region" "this" {
  name = var.region_name
}

data "vcfa_distributed_vlan_connection" "this" {
  name      = var.distributed_vlan_connection_name
  region_id = data.vcfa_region.this.id
}
