# AgentMinder (the Helm chart calls it SSP, Security Services Platform),
# installed small: the identity and policy services, the agent gateway, and
# the MCP server. No observability pipeline, no log shipping, no metrics,
# no local model for the MCP playground, and no self-service console.
#
# Three releases, in order:
#
#   ingress-nginx   the ingress controller AgentMinder's Ingress needs.
#                   Its Service is an Avi LoadBalancer from the cluster's
#                   AKO, which also gives it its DNS name.
#   infra-ssp       chart ssp-infra: the Percona MySQL database.
#   ssp             chart ssp: AgentMinder itself.

locals {
  ssp_repository = "https://ssp_helm_charts.storage.googleapis.com"
  ssp_namespace  = "ssp"
  registry_host  = "securityservices.packages.broadcom.com"
  pull_secret    = "ssp-registry"
}

resource "helm_release" "ingress_nginx" {
  name             = "ingress-nginx"
  namespace        = "ingress-nginx"
  create_namespace = true
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = var.ingress_nginx_chart_version

  # AgentMinder's Ingress uses snippet annotations, which ingress-nginx
  # refuses by default. It names the class nginx, so nginx is not the
  # default class: AKO's avi-lb already is.
  #
  # The Service goes to the cluster's AKO, not the Supervisor: AKO serves
  # only Services of its loadBalancerClass (defaultLBController is false).
  # AKO puts the external-dns hostname on the Avi virtual service, and Avi
  # DNS, authoritative for goad.gpu.set.lab, answers for it. The lab DNS
  # delegates that zone to Avi: see the avi-dns scripts.
  values = [yamlencode({
    controller = {
      allowSnippetAnnotations = true
      config                  = { "annotations-risk-level" = "Critical" }
      ingressClassResource    = { default = false }
      service = {
        type              = "LoadBalancer"
        loadBalancerClass = "ako.vmware.com/avi-lb"
        annotations = {
          "external-dns.alpha.kubernetes.io/hostname" = var.agentminder_hostname
        }
      }
    }
  })]
}

# A new VKS cluster has no default StorageClass, and the ssp-infra chart
# has no setting for its database volume's class. Without a default the
# volume stays Pending: "pod has unbound immediate PersistentVolumeClaims".
resource "kubernetes_annotations" "default_storage_class" {
  api_version = "storage.k8s.io/v1"
  kind        = "StorageClass"
  metadata {
    name = var.storage_class_name
  }
  annotations = {
    "storageclass.kubernetes.io/is-default-class" = "true"
  }
  force = true
}

# Privileged, as in the lab's other AgentMinder. A stricter Pod Security
# profile has not been tried.
resource "kubernetes_namespace_v1" "ssp" {
  metadata {
    name = local.ssp_namespace
    labels = {
      "pod-security.kubernetes.io/enforce" = "privileged"
      "pod-security.kubernetes.io/audit"   = "privileged"
      "pod-security.kubernetes.io/warn"    = "privileged"
    }
  }
}

# One pull secret for every image from Broadcom's registry. Both charts can
# make their own from credentials in their values, but then the password
# is in two Helm releases as well as here.
resource "kubernetes_secret_v1" "ssp_registry" {
  metadata {
    name      = local.pull_secret
    namespace = kubernetes_namespace_v1.ssp.metadata[0].name
  }
  type = "kubernetes.io/dockerconfigjson"
  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        (local.registry_host) = {
          username = var.ssp_registry_username
          password = var.ssp_registry_password
          auth     = base64encode("${var.ssp_registry_username}:${var.ssp_registry_password}")
        }
      }
    })
  }
}

resource "helm_release" "ssp_infra" {
  name       = "infra-ssp"
  namespace  = kubernetes_namespace_v1.ssp.metadata[0].name
  repository = local.ssp_repository
  chart      = "ssp-infra"
  version    = var.ssp_chart_version
  timeout    = 900

  values = [yamlencode({
    # The release name of the ssp chart, which reads this database.
    sspReleaseName = "ssp"
    global = {
      registry = { existingSecrets = [{ name = local.pull_secret }] }
    }
    # Log shipping. Logs stay in the pods.
    fluent-bit = { enabled = false }
    # One node, the chart's default, on a smaller volume than its 80Gi.
    db = { persistence = { size = "20Gi" } }
  })]

  depends_on = [kubernetes_secret_v1.ssp_registry, kubernetes_annotations.default_storage_class]
}

# The chart asks for 400m CPU for each service, and 1000m for iarisk. At
# demo load each one uses under 15m, and the requests alone filled two
# 4-CPU workers: aigateway and iarisk stayed Pending, "Insufficient cpu".
# Only the requests are lowered. The limits stay the chart's, so a busy
# service can still burst.
#
# With deployment.size demo, most services take their resources from
# sizing.demo. The services listed here set their own and ignore it.
locals {
  ssp_cpu_request = "100m"
  ssp_own_resources = [
    "aigateway", "dataseed", "iarisk", "opa", "proxysidecar",
  ]
}

resource "helm_release" "ssp" {
  name       = "ssp"
  namespace  = kubernetes_namespace_v1.ssp.metadata[0].name
  repository = local.ssp_repository
  chart      = "ssp"
  version    = var.ssp_chart_version
  # The first install seeds the database before the services start.
  timeout = 1800

  values = [yamlencode({
    global = {
      imagePullSecrets = [{ name = local.pull_secret }]
    }
    sizing = { demo = { resources = { requests = { cpu = local.ssp_cpu_request } } } }
    hazelcast-enterprise = {
      cluster = { memberCount = 1 }
      image   = { pullSecrets = [local.pull_secret] }
    }
    ssp = merge({
      # The smallest profile: one replica of each service.
      deployment = { size = "demo" }
      global = {
        ssp = { registry = { existingSecrets = [{ name = local.pull_secret }] } }
      }
      ingress = {
        host = var.agentminder_hostname
        tls  = { generateSelfSignedCert = true }
      }
      featureFlags = {
        dataseed  = { enabled = true }
        aigateway = { enabled = true }
        mcpserver = { enabled = true }
        # Off: the OpenTelemetry collector, Prometheus metrics, and the
        # self-service console. The local model for the MCP playground
        # (localLlm) and the observability pipeline (global.observe) are
        # off by default.
        otelCollector      = { enabled = false }
        custommetrics      = { enabled = false }
        selfserviceconsole = { enabled = false }
      }
      },
      { for service in local.ssp_own_resources : service => { resources = { requests = { cpu = local.ssp_cpu_request } } } },
    )
  })]

  depends_on = [helm_release.ingress_nginx, helm_release.ssp_infra]
}
