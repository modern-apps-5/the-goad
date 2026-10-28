# Lab values for the cloud admin root. Not secret, and the same for
# everyone, so they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

vcfa_url = "https://auto.gpu.set.lab"

allow_unverified_ssl = true

region_name = "ans-cluster"

distributed_vlan_connection_name = "vlan-477-connection"

vna_cluster_name = "day-0-vna"

zone_allocations = {
  "west-1" = {
    cpu_limit_mhz          = 963146
    memory_limit_mib       = 2415569
    cpu_reservation_mhz    = 20000
    memory_reservation_mib = 32768
  }
}

vm_class_names = [
  "best-effort-xsmall",
  "best-effort-small",
  "best-effort-medium",
  "best-effort-large",
  "best-effort-xlarge",
  "best-effort-2xlarge",
  "best-effort-4xlarge",
  "best-effort-8xlarge",
  "guaranteed-xsmall",
  "guaranteed-small",
  "guaranteed-medium",
  "guaranteed-large",
  "guaranteed-xlarge",
  "guaranteed-2xlarge",
  "guaranteed-2xlarge-32g",
  "guaranteed-4xlarge",
  "guaranteed-8xlarge",
]

storage_policy_limits_mib = {
  "MGMT-cl01 - Optimal Datastore Default Policy - AutoRAID" = 7200768
}

dsm_infrastructure_policy_names = ["dsm-infra-xscl5"]

ops_url = "https://ops01.gpu.set.lab"

vidb_hostname = "vidb.gpu.set.lab"
