# One Antrea group for each of the shop's services, by the pod labels
# gitops/music-store-apps/workloads.yaml sets. NSX matches Kubernetes
# labels as tags of the form dis:k8s:<key>|<value>.
#
# The users service is a VM and the catalog is in DSM, so neither is a
# pod, and neither has a group here.
locals {
  music_store_services = toset(["store", "cart", "order", "chat"])
}

resource "nsxt_policy_group" "music_store_service" {
  for_each = local.music_store_services

  display_name = "music-store-${each.key}"
  description  = "Music store ${each.key} pods"
  domain       = "default"
  group_type   = "ANTREA"

  criteria {
    condition {
      member_type = "Namespace"
      key         = "Name"
      operator    = "EQUALS"
      value       = var.music_store_namespace
    }
    condition {
      member_type = "Pod"
      key         = "Tag"
      operator    = "EQUALS"
      value       = "dis:k8s:app-name|music-store"
    }
    condition {
      member_type = "Pod"
      key         = "Tag"
      operator    = "EQUALS"
      value       = "dis:k8s:env|prod"
    }
    condition {
      member_type = "Pod"
      key         = "Tag"
      operator    = "EQUALS"
      value       = "dis:k8s:service-name|${each.key}"
    }
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}
