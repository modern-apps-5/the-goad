terraform {
  required_version = ">= 1.11"
  required_providers {
    vcfa = {
      source  = "vmware/vcfa"
      version = "~> 1.2"
    }
    terracurl = {
      source  = "devops-rob/terracurl"
      version = "~> 2.11"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.5"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.13"
    }
  }
}
