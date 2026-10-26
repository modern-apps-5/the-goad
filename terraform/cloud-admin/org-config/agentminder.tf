# Where AgentMinder runs: a project of the cloud admin's own, a namespace
# in it, and a small VKS cluster in the namespace. AgentMinder itself, the
# Helm charts, is terraform/cloud-admin/agentminder. It is a separate root
# because its Helm and Kubernetes providers read the address of this
# cluster, which does not exist until this root has applied.

resource "kubectl_manifest" "cloud_admin_project" {
  provider = kubectl.org

  # A client-side apply sets the last-applied annotation after create, and
  # the API refuses it: "Only project spec can be updated".
  server_side_apply = true
  validate_schema   = false
  yaml_body = yamlencode({
    apiVersion = "project.cci.vmware.com/v1alpha2"
    kind       = "Project"
    metadata   = { name = var.cloud_admin_project }
    spec = {
      description = "Cloud admin services. Managed by terraform/cloud-admin/org-config."
    }
  })
}

resource "vcfa_supervisor_namespace" "agentminder" {
  name_prefix  = "agentminder"
  description  = "AgentMinder. Managed by terraform/cloud-admin/org-config."
  project_name = kubectl_manifest.cloud_admin_project.name
  region_name  = var.region_name
  vpc_name     = var.vpc_name
  class_name   = "small"
  seg_name     = var.service_engine_group_name

  # Room for the cluster: one control plane, the workers, their disks, and
  # AgentMinder's database volume. Best-effort VMs, so no reservation.
  storage_classes_class_config_overrides {
    name  = var.storage_class_name
    limit = "300Gi"
  }

  zones_class_config_overrides {
    name               = var.zone_name
    cpu_limit          = "40000M"
    cpu_reservation    = "0M"
    memory_limit       = "64Gi"
    memory_reservation = "0Mi"
  }

  depends_on = [time_sleep.service_engine_group]
}

# Read the generated name through a local value, as in
# terraform/platform-engineer: see decision 23.
locals {
  agentminder_namespace = vcfa_supervisor_namespace.agentminder.name
}

resource "vcfa_vks_cluster" "agentminder" {
  name    = var.agentminder_cluster.name
  version = var.agentminder_cluster.kubernetes_version

  # The platform-observability Supervisor Service onboards labelled
  # clusters to VCF Operations and installs its collectors. VKS already
  # turns on helm-controller, which the addon needs.
  labels = {
    "addons.kubernetes.vmware.com/platform-observability" = "enabled"
  }

  context = {
    project   = var.cloud_admin_project
    namespace = local.agentminder_namespace
  }

  cluster_class = {
    name      = var.agentminder_cluster.cluster_class
    namespace = "vmware-system-vks-public"
  }

  cluster_network = {
    pods     = { cidr_blocks = ["192.168.0.0/16"] }
    services = { cidr_blocks = ["10.96.0.0/12"] }
  }

  control_plane = {
    replicas = 1
    os_image = { name = "ubuntu", version = "24.04" }
  }

  machine_deployments = [{
    name     = "workers"
    class    = "node-pool"
    replicas = var.agentminder_cluster.workers
    os_image = { name = "ubuntu", version = "24.04" }
    variable_overrides = [
      { name = "vmClass", value = jsonencode(var.agentminder_cluster.worker_class) },
      # AgentMinder's images are large. The node's own disk fills up
      # without a separate volume for containerd.
      {
        name = "volumes"
        value = jsonencode([{
          name         = "containerd"
          mountPath    = "/var/lib/containerd"
          capacity     = var.agentminder_cluster.containerd_disk_size
          storageClass = var.storage_class_name
        }])
      },
    ]
  }]

  variables = [
    { name = "vmClass", value = jsonencode(var.agentminder_cluster.control_plane_class) },
    { name = "storageClass", value = jsonencode(var.storage_class_name) },
    {
      name = "bootstrapAddons"
      value = jsonencode({
        cniRef = { name = "antrea", namespace = "vmware-system-vks-public" }
      })
    },
  ]

  wait_for = {
    available = true
    deleted   = true
  }

  timeouts = {
    create = "60m"
    update = "60m"
    delete = "30m"
  }
}
