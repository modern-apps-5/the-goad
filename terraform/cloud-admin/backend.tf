# State is remote. The address and the login are not in git: see
# backend.hcl.example.
terraform {
  backend "http" {}
}
