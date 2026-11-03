# Lab values for the cloud admin's VCF Operations root. Not secret, and the
# same for everyone, so they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

ops_url = "https://ops01.gpu.set.lab"

allow_unverified_ssl = true
