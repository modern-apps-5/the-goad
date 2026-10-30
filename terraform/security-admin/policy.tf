# Layer 1 of the music store's policy (decision 49): the flows the
# security admin mandates, whatever the developer does. NSX pushes this
# policy into the cluster as an Antrea ClusterNetworkPolicy in the tier
# nsx-category-application, which Antrea evaluates before every native
# tier.
#
# Allow rules only. A catch-all drop here would decide every flow before
# the developer's application tier is reached, so their rules could never
# allow anything. The default deny is the platform engineer's, in the
# baseline tier. Never edit the pushed policy with kubectl: the
# ccp-adapter puts it back.

# NSX names an Antrea cluster <Supervisor id>-<Supervisor Namespace>-<cluster>-antrea.
# The Supervisor Namespace has a generated suffix, so the cluster is
# found by pattern, and exactly one must match.
data "nsxt_policy_container_clusters" "all" {}

locals {
  music_store_cluster_pattern = "-${var.supervisor_namespace_prefix}-[a-z0-9]+-${var.cluster_name}-antrea$"
  music_store_cluster_path = one([
    for name, path in data.nsxt_policy_container_clusters.all.items : path
    if can(regex(local.music_store_cluster_pattern, name))
  ])
}

resource "nsxt_policy_parent_security_policy" "music_store" {
  display_name    = "music-store"
  description     = "Security admin guardrails for the music store, pushed to its VKS cluster through Antrea"
  category        = "Application"
  domain          = "default"
  sequence_number = 499999
  stateful        = true
  tcp_strict      = true

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}

resource "nsxt_policy_security_policy_container_cluster" "music_store" {
  display_name           = "music-store"
  description            = "Applies the music store policy to its VKS cluster"
  policy_path            = nsxt_policy_parent_security_policy.music_store.path
  container_cluster_path = local.music_store_cluster_path

  lifecycle {
    precondition {
      condition     = local.music_store_cluster_path != null
      error_message = "No Antrea container cluster in NSX matches ${local.music_store_cluster_pattern}. Is Antrea's NSX integration on (gitops/music-store/antrea-nsx.yaml)?"
    }
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}

# The shop is reached only through Avi. AKO uses NodePortLocal: the pool
# members are node addresses on NodePortLocal ports, and the traffic keeps
# the service engine's data address as its source. So no node address is
# needed here, and scaling the cluster changes nothing.
resource "nsxt_policy_security_policy_rule" "frontend_from_avi" {
  display_name    = "frontend-from-avi"
  description     = "Avi service engines to the store, TCP 5000"
  policy_path     = nsxt_policy_parent_security_policy.music_store.path
  sequence_number = 249999
  action          = "ALLOW"
  direction       = "IN"
  ip_version      = "IPV4_IPV6"
  logged          = true

  source_groups = var.frontend_source_cidrs
  services      = [nsxt_policy_service.music_store_port["frontend"].path]
  # Antrea rules take what they apply to from scope, not destination_groups.
  scope = [nsxt_policy_group.music_store_service["store"].path]

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}
