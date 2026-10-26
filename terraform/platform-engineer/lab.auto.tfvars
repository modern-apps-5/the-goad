# Lab values for the platform engineer root. Not secret, and the same for
# everyone, so they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

vcfa_url = "https://auto.gpu.set.lab"

allow_unverified_ssl = true

region_name = "ans-cluster"

vpc_name = "default-ans-cluster"

zone_name = "west-1"

storage_class_name = "mgmt-cl01-optimal-datastore-default-policy-autoraid"

content_library_storage_policy = "MGMT-cl01 - Optimal Datastore Default Policy - AutoRAID"

gitops_repo_ssh_key_file = ".secrets/gitops-deploy-key"

# The Private AI Services ingress in the private-ai namespace, and the
# model the shop's chat asks for.
music_store_chat = {
  base_url = "https://10.47.7.73/api/v1/compatibility/openai/v1"
  model    = "qwen"
}
