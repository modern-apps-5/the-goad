# Ports the security admin's rules name. The shop's service-to-service
# ports are the developer's, in gitops/music-store-apps, and are not here.
locals {
  music_store_ports = {
    frontend = 5000
  }
}

resource "nsxt_policy_service" "music_store_port" {
  for_each = local.music_store_ports

  display_name = "music-store-${each.key}-tcp-${each.value}"
  description  = "Music store ${each.key}, TCP ${each.value}"

  l4_port_set_entry {
    display_name      = "tcp-${each.value}"
    protocol          = "TCP"
    destination_ports = [tostring(each.value)]
  }

  tag {
    scope = "managed-by"
    tag   = "terraform"
  }
}
