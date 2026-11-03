# Lab values for the agentic ops engineer's root. Not
# secret, and the same for everyone, so they are in git. Terraform loads
# this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

insecure_skip_tls_verify = true

agentminder_hostname = "agentminder.goad.gpu.set.lab"
apps_domain          = "apps.goad.gpu.set.lab"
