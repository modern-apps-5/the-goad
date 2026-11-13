# A proxy cache in the Supervisor's Harbor for Broadcom's Tanzu Platform
# content registry, tanzu-platform-content.packages.broadcom.com. That
# registry holds the Bitnami images that Tanzu Hub lists, and every pull
# from it needs a Broadcom login.
#
# The project proxies the whole registry, not one image. It is public, so
# anything in the lab pulls without a login, by the same path with the
# project in front:
#
#   tanzu-platform-content.packages.broadcom.com/containers/photon-5/python:<tag>
#   <harbor>/tanzu-platform-content/containers/photon-5/python:<tag>
#
# Harbor fetches an image on its first pull and serves the cached copy
# after that. Only Harbor holds the Broadcom login. See decision 46.

resource "harbor_registry" "tanzu_platform_content" {
  provider_name = "docker-registry"
  name          = "tanzu-platform-content"
  description   = "Broadcom's Tanzu Platform content registry. Managed by terraform/cloud-admin/org."
  endpoint_url  = "https://tanzu-platform-content.packages.broadcom.com"
  access_id     = var.broadcom_registry_username
  access_secret = var.broadcom_registry_token
}

resource "harbor_project" "tanzu_platform_content" {
  name        = "tanzu-platform-content"
  public      = true
  registry_id = harbor_registry.tanzu_platform_content.registry_id
}

# The music store's images. The platform engineer's build workflow pushes
# them with the robot account below, and the music store's VKS cluster
# pulls them with no login: the project is public, and VKS trusts the
# Supervisor's Harbor already. See decision 47.
resource "harbor_project" "music_store" {
  name   = "music-store"
  public = true
}

# The platform engineer's push login for music-store, and nothing else.
# Harbor names it robot$music-store+builder.
#
# Its secret is the team's shared value, set here and read by the
# platform engineer's workflow from the same GitHub secret. It is
# write-only, so it is never in state. To change it, change the value and
# raise music_store_robot_secret_version.
resource "harbor_robot_account" "music_store_builder" {
  name        = "builder"
  description = "The platform engineer's image builds. Managed by terraform/cloud-admin/org."
  level       = "project"
  duration    = -1

  secret_wo         = var.music_store_robot_secret
  secret_wo_version = var.music_store_robot_secret_version

  permissions {
    kind      = "project"
    namespace = harbor_project.music_store.name

    access {
      action   = "push"
      resource = "repository"
    }
    access {
      action   = "pull"
      resource = "repository"
    }
  }
}

# Keep every image the proxy has cached. Harbor gives a proxy cache
# project its own retention policy, which keeps only what was pulled in
# the last 7 days. The music store's base image is pulled only by builds,
# so a week without one emptied the cache, and the next build had to
# fetch from Broadcom again, where an expired token fails every pull
# (decision 54).
resource "harbor_retention_policy" "tanzu_platform_content" {
  scope = harbor_project.tanzu_platform_content.id

  rule {
    repo_matching = "**"
    tag_matching  = "**"
    always_retain = true
  }
}

# Harbor made the policy with the project. Remove this block once it is
# in every state.
import {
  to = harbor_retention_policy.tanzu_platform_content
  id = "/retentions/2"
}
