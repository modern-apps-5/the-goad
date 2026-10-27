# The VM image for the shop's users VM in gitops/music-store-dev/users-vm/users-vm.yaml.
#
# A VM Service VM names its image by display name, and the org has no image
# until it has a content library. This creates one for the org, attached to
# every namespace in it, and uploads Ubuntu's cloud image under the name the
# VM uses.
#
# The image is downloaded once, on the machine or runner that first applies
# this. After that the item is in state, and nobody needs the file: the
# provider reads file_paths only to create the item.

data "vcfa_org" "org" {
  name = var.org_name
}

data "vcfa_region" "region" {
  name = var.region_name
}

# A tenant reads the storage class by the storage policy's name, not by its
# Kubernetes name.
data "vcfa_storage_class" "content_library" {
  region_id = data.vcfa_region.region.id
  name      = var.content_library_storage_policy
}

resource "vcfa_content_library" "images" {
  org_id            = data.vcfa_org.org.id
  name              = "goad-images"
  description       = "VM images for GOAD. Managed by terraform/platform-engineer."
  storage_class_ids = [data.vcfa_storage_class.content_library.id]
  auto_attach       = true
  delete_recursive  = true
}

locals {
  ubuntu_image_file = "${path.module}/.images/${basename(var.ubuntu_image.url)}"
}

resource "terraform_data" "ubuntu_image_download" {
  triggers_replace = [var.ubuntu_image.url]

  provisioner "local-exec" {
    command = "mkdir -p \"$(dirname \"$FILE\")\" && curl -fsSL --retry 3 -o \"$FILE\" \"$URL\""
    environment = {
      FILE = local.ubuntu_image_file
      URL  = var.ubuntu_image.url
    }
  }
}

resource "vcfa_content_library_item" "ubuntu" {
  name               = var.ubuntu_image.name
  description        = "Ubuntu cloud image, from ${var.ubuntu_image.url}. Managed by terraform/platform-engineer."
  content_library_id = vcfa_content_library.images.id
  file_paths         = [local.ubuntu_image_file]

  depends_on = [terraform_data.ubuntu_image_download]
}
