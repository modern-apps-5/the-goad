# Lets the org create databases with Data Services Manager (DSM).
#
# A data service policy belongs to DSM, and the vcfa provider has no
# resource for it. DSM serves a Kubernetes API, and VCF Automation proxies
# it per region, so the kubernetes provider manages the policy through
# VCF Automation with the provider session token. This is the object the
# provider portal creates under Data Services.
provider "kubernetes" {
  alias    = "dsm"
  host     = "${trimsuffix(var.vcfa_url, "/")}/proxy/external-endpoint/api/dsm/regions/${var.region_name}"
  token    = local.vcfa_token
  insecure = var.allow_unverified_ssl
}

# Skipped when var.dsm_infrastructure_policy_names is empty.
resource "kubernetes_manifest" "dsm_postgres_policy" {
  count    = length(var.dsm_infrastructure_policy_names) == 0 ? 0 : 1
  provider = kubernetes.dsm

  manifest = {
    apiVersion = "infrastructure.dataservices.vmware.com/v1alpha1"
    kind       = "DataServicePolicy"
    metadata = {
      name      = var.org_name
      namespace = "dsm-system"
      # The portal lists only policies with this label.
      labels = { "dsm.vmware.com/created-in" = "vcfa" }
    }
    spec = {
      description = "PostgreSQL for org ${var.org_name}. Managed by terraform/cloud-admin."
      serviceType = "vmware-sql-postgres"
      # The policy applies to every namespace of this org.
      matchCriteria = [{
        key      = "vcfa.vmware.com/org"
        operator = "in"
        values   = [vcfa_org.this.id]
      }]
      postgresPolicy = {
        allowedVersions = ["*"]
        allowedReplicas = [-1]
        backupConfig    = { allowedStates = ["on", "off"] }
        common = {
          allowedInfrastructurePolicies  = var.dsm_infrastructure_policy_names
          allowedBackupLocations         = []
          allowedMaintenanceWindowStates = ["on", "off"]
          databaseConfig                 = { allowedParameters = ["*"] }
        }
      }
    }
  }
}
