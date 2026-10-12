# Lab values for the runner root. Not secret, and the same for everyone, so
# they are in git. Terraform loads this file by itself.
#
# Secrets are not here. They are in terraform.tfvars, which git ignores:
# see terraform.tfvars.example.

vcenter_server = "vc01.gpu.set.lab"

vcenter_user = "administrator@gpu.local"

allow_unverified_ssl = true

supervisor_endpoint = "10.47.7.8"

# supervisor-01
supervisor_id = "1879aa59-b358-42a1-ad9e-0f9f711aa9f2"

storage_policy_name = "Management Storage policy - Thin"

github_url = "https://github.com/modern-apps-5"

# One workflow for each persona, and the two can run at the same time. With
# one runner, the second would wait.
runner_replicas = 2

# To take a newer runner image, put a newer commit here.
runner_commit = "fcca73b8b108e03d6145f8a9c2fab4df8a0946e8"

# Set this once the GitHub App exists: scripts/create-github-app.py
# prints the ID.
# The ID is not a secret. Until it is set, Terraform creates the namespace
# and no runner.
github_app_id = "5288268"
