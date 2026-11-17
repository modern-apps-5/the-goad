locals {
  runner_enabled = var.github_app_id != null

  runner_source = "https://raw.githubusercontent.com/warroyo/supervisor-github-runner/${var.runner_commit}/base"
}

# What the runner logs in to GitHub with. It trades the key for a token that
# lasts one hour, each time a pod starts.
resource "kubectl_manifest" "github_app" {
  count = local.runner_enabled ? 1 : 0

  sensitive_fields = ["stringData"]
  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "Secret"
    metadata = {
      name      = "github-app"
      namespace = vsphere_namespace.runner.name
    }
    stringData = {
      "app-id"          = var.github_app_id
      "private-key.pem" = file(var.github_app_private_key_file)
    }
  })
}

# The runner is supervisor-github-runner: a Deployment, and the scripts its
# two containers start with. Both are read from that repository at one commit,
# so nothing is copied here and nothing changes until runner_commit does.
data "http" "runner_deployment" {
  url = "${local.runner_source}/deployment.yaml"

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Cannot read deployment.yaml at commit ${var.runner_commit}: HTTP ${self.status_code}."
    }
  }
}

data "http" "runner_entrypoint" {
  url = "${local.runner_source}/entrypoint.sh"

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Cannot read entrypoint.sh at commit ${var.runner_commit}: HTTP ${self.status_code}."
    }
  }
}

data "http" "runner_minter" {
  url = "${local.runner_source}/mint.sh"

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Cannot read mint.sh at commit ${var.runner_commit}: HTTP ${self.status_code}."
    }
  }
}

locals {
  # What the runner serves, and the labels a workflow asks for. These are
  # all the labels: nothing is added to them.
  runner_settings = {
    GITHUB_URL    = var.github_url
    RUNNER_LABELS = join(",", var.runner_labels)
  }

  upstream_deployment = yamldecode(data.http.runner_deployment.response_body)

  # The upstream Deployment, with three things changed: the number of
  # replicas, the runner container's CPU and memory, and an annotation on
  # the pod. A pod reads the scripts and the settings only when it starts.
  # The annotation changes when they do, and that restarts the pods. The
  # runner is the first container. The minter beside it keeps upstream's
  # resources.
  #
  # A vSphere Pod's VM is sized from the limits. Upstream gives 2 CPU and
  # 2Gi. The Tanzu cf CLI's first run starts dozens of copies of its plugin
  # at once to build a command cache, which does not fit in 2Gi. Ephemeral
  # storage stays upstream's: it must match the work volume's sizeLimit.
  upstream_pod = local.upstream_deployment.spec.template.spec
  runner_containers = [
    for i, c in local.upstream_pod.containers : i != 0 ? c : merge(c, {
      resources = {
        requests = merge(c.resources.requests, var.runner_resources.requests)
        limits   = merge(c.resources.limits, var.runner_resources.limits)
      }
    })
  ]

  runner_deployment = merge(local.upstream_deployment, {
    spec = merge(local.upstream_deployment.spec, {
      replicas = var.runner_replicas
      template = merge(local.upstream_deployment.spec.template, {
        metadata = merge(local.upstream_deployment.spec.template.metadata, {
          annotations = {
            "goad/entrypoint-sha256" = sha256(data.http.runner_entrypoint.response_body)
            "goad/minter-sha256"     = sha256(data.http.runner_minter.response_body)
            "goad/settings-sha256"   = sha256(jsonencode(local.runner_settings))
          }
        })
        spec = merge(local.upstream_pod, { containers = local.runner_containers })
      })
    })
  })
}

# The Deployment reads this ConfigMap by this exact name.
resource "kubectl_manifest" "runner_settings" {
  count = local.runner_enabled ? 1 : 0

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "github-runner"
      namespace = vsphere_namespace.runner.name
    }
    data = local.runner_settings
  })
}

resource "kubectl_manifest" "runner_entrypoint" {
  count = local.runner_enabled ? 1 : 0

  yaml_body = yamlencode({
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {
      name      = "github-runner-entrypoint"
      namespace = vsphere_namespace.runner.name
    }
    data = {
      "entrypoint.sh" = data.http.runner_entrypoint.response_body
      "mint.sh"       = data.http.runner_minter.response_body
    }
  })
}

# A change here restarts the pods, and that stops a running job. Check that
# the runner is idle before an apply: see README.md.
resource "kubectl_manifest" "runner_deployment" {
  count = local.runner_enabled ? 1 : 0

  # The upstream manifest does not name a namespace.
  override_namespace = vsphere_namespace.runner.name
  yaml_body          = yamlencode(local.runner_deployment)

  depends_on = [
    kubectl_manifest.github_app,
    kubectl_manifest.runner_settings,
    kubectl_manifest.runner_entrypoint,
  ]
}
