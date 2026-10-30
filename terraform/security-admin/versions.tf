terraform {
  required_version = ">= 1.11"
  required_providers {
    # 3.11.0 added the Antrea container cluster data source and the
    # resource that ties a security policy to it.
    nsxt = {
      source  = "vmware/nsxt"
      version = "~> 3.12"
    }
  }
}
