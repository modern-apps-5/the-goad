data "vsphere_storage_policy" "runner" {
  name = var.storage_policy_name
}

# A Supervisor Namespace made in vCenter, not through VCF Automation: see
# decision 25. It has no project, no generated suffix, and VCF Automation
# does not list it.
#
# No network is set, so it gets the Supervisor's workload network. No VM
# classes and no limits: the runner is vSphere Pods, and it is small.
resource "vsphere_namespace" "runner" {
  name       = var.namespace_name
  supervisor = var.supervisor_id

  storage_policies = [data.vsphere_storage_policy.runner.id]
}
