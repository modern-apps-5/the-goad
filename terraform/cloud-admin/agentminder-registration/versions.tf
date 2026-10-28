terraform {
  required_version = ">= 1.11"
  required_providers {
    vcfa = {
      source  = "vmware/vcfa"
      version = "~> 1.2"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
    restapi = {
      source  = "Mastercard/restapi"
      version = "~> 3.0"
    }
    cloudfoundry = {
      source  = "cloudfoundry/cloudfoundry"
      version = "~> 1.18"
    }
  }
}
