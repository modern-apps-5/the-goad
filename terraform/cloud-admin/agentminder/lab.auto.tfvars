# Lab values for the cloud admin's AgentMinder root. Not secret, and the
# same for everyone, so they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

vcfa_url = "https://auto.gpu.set.lab"

allow_unverified_ssl = true

agentminder_hostname = "agentminder.goad.gpu.set.lab"
storage_class_name   = "mgmt-cl01-optimal-datastore-default-policy-autoraid"
