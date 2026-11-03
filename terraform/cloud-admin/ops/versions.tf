terraform {
  required_version = ">= 1.11"
  required_providers {
    terracurl = {
      source  = "devops-rob/terracurl"
      version = "~> 2.11"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.5"
    }
  }
}
