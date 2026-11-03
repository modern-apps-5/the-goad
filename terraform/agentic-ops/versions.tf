terraform {
  required_version = ">= 1.11"
  required_providers {
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
