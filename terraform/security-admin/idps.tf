# Distributed IDPS on the users VM music-users (issue #112). The VM is a
# VM Service VM in the goad org's NSX project, not a pod, so none of the
# Antrea policy in policy.tf reaches it. vDefend inspects its traffic on
# its vNIC instead, inside the project.
#
# The objects have fixed NSX IDs, so the demo script finds the rule at
# a known path.
#
# The rule's action is the virtual patch. DETECT, the baseline here, logs
# an event and lets the request through. DETECT_PREVENT resets the
# connection when a signature in the profile matches. The demo
# demos/vdefend-virtual-patching switches the action in NSX directly, to
# be quick on stage, and switches it back. That is drift from this root
# while it lasts: the next apply puts DETECT back.
#
# IDPS must be on for the region's vSphere cluster. That is a lab setting
# for the whole cluster, not this root's: docs/build.md, "Before you
# start". The precondition below stops the plan when it is off.

data "nsxt_policy_project" "goad" {
  display_name = var.nsx_project_name
}

data "nsxt_policy_idps_cluster_config" "region" {
  id = var.idps_cluster_config_id
}

# VM Operator copies the VM's labels to its NSX subnet port as tags, so
# the label app: users-service in gitops/music-store/users-vm.yaml is the
# match. The group is in the project, so it never reaches another org's
# VM with the same label.
resource "nsxt_policy_group" "music_users" {
  nsx_id       = "music-users"
  display_name = "music-users"
  description  = "The music store's users VM, by its subnet port's tag"
  domain       = "default"

  context {
    project_id = data.nsxt_policy_project.goad.id
  }

  criteria {
    condition {
      member_type = "SegmentPort"
      key         = "Tag"
      operator    = "EQUALS"
      value       = "app|users-service"
    }
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}

# The signatures this profile turns into a virtual patch: Apache HTTP
# Server 2.4.49 and 2.4.50 path traversal, CVE-2021-41773 and
# CVE-2021-42013. The overrides keep them on and rejecting, whatever a
# signature bundle update sets as their default. Each is in the bundle
# IDPSSignatures.3822 that ships with NSX 9.1.
locals {
  apache_path_traversal_signatures = toset([
    "1116173", # NSX - Detect CVE-2021-41773 exploitation attempts (.%2e/)
    "1116174", # NSX - Detect CVE-2021-41773 exploitation attempts (%2e%2e/)
    "2034124", # ET EXPLOIT Apache HTTP Server 2.4.49 - Path Traversal Attempt M1
    "2034125", # ET EXPLOIT Apache HTTP Server 2.4.49 - Path Traversal Attempt M2
    "2034128", # ET EXPLOIT Apache HTTP Server 2.4.49 - Path Traversal Attempt M3
    "4103199", # SLR Alert - Apache 2.4.49 Path Traversal
  ])
}

# Every signature of medium severity or above, not only the CVE's: in
# DETECT_PREVENT any of them resets the connection. The users service
# answers only small JSON requests, so a false positive is unlikely.
resource "nsxt_policy_intrusion_service_profile" "music_users" {
  nsx_id       = "music-users"
  display_name = "music-users"
  description  = "IDPS profile for the music store's users VM, with the Apache path traversal virtual patch"
  severities   = ["CRITICAL", "HIGH", "MEDIUM"]

  context {
    project_id = data.nsxt_policy_project.goad.id
  }

  dynamic "overridden_signature" {
    for_each = local.apache_path_traversal_signatures
    content {
      signature_id = overridden_signature.value
      action       = "REJECT"
      enabled      = true
    }
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}

resource "nsxt_policy_parent_intrusion_service_policy" "music_users" {
  nsx_id          = "music-users"
  display_name    = "music-users"
  description     = "Distributed IDPS for the music store's users VM"
  domain          = "default"
  category        = "ThreatRules"
  sequence_number = 1

  context {
    project_id = data.nsxt_policy_project.goad.id
  }

  lifecycle {
    precondition {
      condition     = data.nsxt_policy_idps_cluster_config.region.ids_enabled
      error_message = "IDPS is off for the vSphere cluster ${var.idps_cluster_config_id}. Turn on its DFW and IDPS first: docs/build.md, Before you start."
    }
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}

resource "nsxt_policy_intrusion_service_policy_rule" "music_users" {
  nsx_id          = "users-vm-inbound"
  display_name    = "users-vm-inbound"
  description     = "Inspect traffic to the users VM. DETECT logs, DETECT_PREVENT is the virtual patch"
  policy_path     = nsxt_policy_parent_intrusion_service_policy.music_users.path
  sequence_number = 1
  action          = "DETECT"
  direction       = "IN"
  ip_version      = "IPV4_IPV6"
  logged          = true

  destination_groups = [nsxt_policy_group.music_users.path]
  scope              = [nsxt_policy_group.music_users.path]
  ids_profiles       = [nsxt_policy_intrusion_service_profile.music_users.path]

  context {
    project_id = data.nsxt_policy_project.goad.id
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}
