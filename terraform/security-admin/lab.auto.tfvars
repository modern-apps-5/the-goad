# Lab values for the security admin's root. Not secret, and the same for
# everyone, so they are in git. Terraform loads this file by itself.
#
# The NSX password is not here. It is in terraform.tfvars, which git
# ignores: see terraform.tfvars.example.

nsx_manager          = "nsx01.gpu.set.lab"
allow_unverified_ssl = true
nsx_username         = "admin"

# The data network of goad-se-group's service engines (100.64.32.7 and .8),
# not the VIP network.
frontend_source_cidrs = ["100.64.32.0/24"]

# MGMT-cl01 in vCenter vc01. DFW and IDPS were turned on for it by hand
# (docs/build.md, Before you start).
idps_cluster_config_id = "6605d825-020a-4941-ad43-c1fab4a8d1ca:domain-c9"
