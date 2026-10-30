# The security admin works in NSX Manager. vDefend policy written here
# reaches the VKS cluster music-store as Antrea ClusterNetworkPolicies,
# through the cluster's Antrea NSX integration (decision 49).
provider "nsxt" {
  host                 = var.nsx_manager
  username             = var.nsx_username
  password             = var.nsx_password
  allow_unverified_ssl = var.allow_unverified_ssl
}
