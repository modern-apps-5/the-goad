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
