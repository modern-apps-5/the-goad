# State is in the Terraform state registry of the lab's Gitea server.
# Everything here is the same for everyone, so it is in git.
#
# The one thing missing is the token of the shared Gitea user. A backend
# block cannot read a variable, so the token comes from backend.hcl, which
# git ignores:
#
#   terraform init -backend-config=backend.hcl
#
# The state is still named goad-runner: the root was terraform/runner
# before it also registered addons (decision 56). Renaming the state would
# mean moving it in Gitea, for no change in what it holds.
terraform {
  backend "http" {
    address        = "https://git.gpu.set.lab/api/packages/the-goad/terraform/state/goad-runner"
    lock_address   = "https://git.gpu.set.lab/api/packages/the-goad/terraform/state/goad-runner/lock"
    unlock_address = "https://git.gpu.set.lab/api/packages/the-goad/terraform/state/goad-runner/lock"
    lock_method    = "POST"
    unlock_method  = "DELETE"
    username       = "goad-terraform"

    # The lab git server has a self-signed certificate.
    skip_cert_verification = true
  }
}
