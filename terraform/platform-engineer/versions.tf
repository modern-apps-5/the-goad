terraform {
  required_version = ">= 1.11"
  required_providers {
    vcfa = {
      source  = "vmware/vcfa"
      version = "~> 1.2"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.4"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.13"
    }
    terracurl = {
      source  = "devops-rob/terracurl"
      version = "~> 2.11"
    }
    cloudfoundry = {
      source  = "cloudfoundry/cloudfoundry"
      version = "~> 1.18"
    }
  }
}
