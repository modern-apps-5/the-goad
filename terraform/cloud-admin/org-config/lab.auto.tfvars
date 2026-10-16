# Lab values for the cloud admin's org-config root. Not secret, and the same
# for everyone, so they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

vcfa_url = "https://auto.gpu.set.lab"

allow_unverified_ssl = true

platform_engineers = [
  "william.arroyo@set.lab",
]

# The AD service account that terraform/platform-engineer logs in as, with
# an API token.
platform_engineer_automation_user = "svc.platform_engineer@set.lab"

# What terraform/cloud-admin/org gave the org.
region_name        = "ans-cluster"
zone_name          = "west-1"
vpc_name           = "default-ans-cluster"
storage_class_name = "mgmt-cl01-optimal-datastore-default-policy-autoraid"
