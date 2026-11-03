# --- Platform observability dashboards ---
#
# Every dashboards/*.json is a Grafana dashboard, imported into VCF
# Operations' platform observability extension (Explore Charts). To add
# one, put its JSON in dashboards/ and apply. In VCF Operations the viewer
# picks the cluster (the Source); a dashboard is not tied to one.
#
# The import is an internal, unsupported API. It takes only a multipart
# upload, and only Grafana JSON with schemaVersion 42 or later. The
# dashboard's own "uid" must be unique among the imported dashboards.
#
# There is no call to update a dashboard, so a changed file makes a new
# import and deletes the old one. A dashboard changed in the UI is not
# seen.
locals {
  dashboards_api      = "${local.ops_internal}/extension/vodap/app0/dashboards"
  dashboards          = { for file in fileset("${path.module}/dashboards", "*.json") : trimsuffix(file, ".json") => file("${path.module}/dashboards/${file}") }
  dashboard_multipart = "goad-dashboard-import"
}

resource "terracurl_request" "dashboard" {
  for_each = local.dashboards

  name   = "dashboard-${each.key}"
  method = "POST"
  url    = "${local.dashboards_api}/import"
  headers = {
    "Content-Type" = "multipart/form-data; boundary=${local.dashboard_multipart}"
  }
  request_body = join("\r\n", [
    "--${local.dashboard_multipart}",
    "Content-Disposition: form-data; name=\"file\"; filename=\"${each.key}.json\"",
    "Content-Type: application/json",
    "",
    each.value,
    "--${local.dashboard_multipart}--",
    "",
  ])
  response_codes  = ["201"]
  skip_tls_verify = var.allow_unverified_ssl

  lifecycle {
    precondition {
      condition     = try(jsondecode(each.value).schemaVersion, 0) >= 42 && try(jsondecode(each.value).uid, "") != ""
      error_message = "dashboards/${each.key}.json needs a uid and schemaVersion 42 or later."
    }
  }

  # skip_destroy defaults to true. Without this line destroy sends nothing.
  skip_destroy            = false
  destroy_url             = "${local.dashboards_api}/{response.data.dashboard_id}"
  destroy_method          = "DELETE"
  destroy_response_codes  = ["204"]
  destroy_skip_tls_verify = var.allow_unverified_ssl
}
