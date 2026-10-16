# The cloud admin's third stage installs AgentMinder on the VKS cluster that
# terraform/cloud-admin/org-config made. It logs in to the org as the org's
# one local user, cloud-admin, only to read that cluster's kubeconfig.
provider "vcfa" {
  url                  = var.vcfa_url
  org                  = var.org_name
  user                 = var.cloud_admin_username
  password             = var.cloud_admin_password
  allow_unverified_ssl = var.allow_unverified_ssl
}

# The project, namespace, and cluster names, from org-config's state. The
# namespace name is generated, so nothing else knows it.
#
# The token of the shared Gitea user comes from TF_HTTP_PASSWORD, as for
# the workflow's own backend. A data source cannot read backend.hcl.
data "terraform_remote_state" "org_config" {
  backend = "http"
  config = {
    address                = "https://git.gpu.set.lab/api/packages/the-goad/terraform/state/goad-cloud-admin-org-config"
    username               = "goad-terraform"
    skip_cert_verification = true
  }
}

locals {
  org_config = data.terraform_remote_state.org_config.outputs
}

# The cluster's admin kubeconfig: a client certificate, not a VCF
# Automation token, so it does not expire during a long Helm install.
data "vcfa_vks_cluster_kubeconfig" "agentminder" {
  name = local.org_config.agentminder_cluster_name
  context = {
    project   = local.org_config.cloud_admin_project
    namespace = local.org_config.agentminder_namespace
  }
}

locals {
  cluster = data.vcfa_vks_cluster_kubeconfig.agentminder
}

provider "kubernetes" {
  host                   = local.cluster.host
  cluster_ca_certificate = base64decode(local.cluster.certificate_authority_data)
  client_certificate     = base64decode(local.cluster.client_certificate_data)
  client_key             = base64decode(local.cluster.client_key_data)
}

provider "helm" {
  kubernetes = {
    host                   = local.cluster.host
    cluster_ca_certificate = base64decode(local.cluster.certificate_authority_data)
    client_certificate     = base64decode(local.cluster.client_certificate_data)
    client_key             = base64decode(local.cluster.client_key_data)
  }
}
