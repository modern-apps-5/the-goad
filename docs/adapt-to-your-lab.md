# Adapt GOAD to your lab

This repository names one lab: its addresses, its policies, its directory
groups, and its GitHub organization. To build GOAD in another lab, change
each value below, commit, then follow [build.md](build.md).

To find every lab name and address that is left:

```sh
git grep -nE 'set\.lab|10\.47\.|172\.21\.|modern-apps-5' -- ':!*/specs/*'
```

## Terraform

### `lab.auto.tfvars`, in each root

Every lab value that is not secret. Change these first.

| Root | Values |
|---|---|
| `terraform/cloud-admin/org` | `vcfa_url`, `region_name`, `distributed_vlan_connection_name`, `vna_cluster_name`, `zone_allocations`, `vm_class_names`, `storage_policy_limits_mib`, `dsm_infrastructure_policy_names`, `ops_url`, `vidb_hostname`, `harbor_url` |
| `terraform/cloud-admin/org-config` | `vcfa_url`, `platform_engineer_group`, `platform_engineer_automation_user`, `region_name`, `zone_name`, `vpc_name`, `storage_class_name` |
| `terraform/cloud-admin/agentminder` | `vcfa_url`, `agentminder_hostname`, `storage_class_name` |
| `terraform/cloud-admin/ops` | `ops_url` |
| `terraform/platform-engineer` | `vcfa_url`, `region_name`, `vpc_name`, `zone_name`, `storage_class_name`, `content_library_storage_policy`, `music_store_chat` |
| `terraform/agentic-ops` | `agentminder_hostname`, `apps_domain` |
| `terraform/security-admin` | `nsx_manager`, `nsx_username`, `frontend_source_cidrs` |
| `terraform/runner` | `vcenter_server`, `vcenter_user`, `supervisor_endpoint`, `supervisor_id`, `storage_policy_name`, `github_url`, `github_app_id` |

`allow_unverified_ssl` and `insecure_skip_tls_verify` are `true` because
the lab uses self-signed certificates. Set them to `false` if yours are
trusted.

### Variable defaults

Some lab values are defaults in `variables.tf`. Override each in that
root's `lab.auto.tfvars`:

| Root | Variable | This lab's value |
|---|---|---|
| `terraform/platform-engineer` | `cf_api_url` | `https://api.sys.goad.gpu.set.lab` |
| `terraform/platform-engineer` | `cf_org_name` | `Goad` |
| `terraform/platform-engineer` | `cf_apps_domain` | `apps.goad.gpu.set.lab` |
| `terraform/platform-engineer` | `incident_k8s_api_server` | The `music-store` cluster's API server address |
| `terraform/platform-engineer` | `gitops_repo` | This repository's SSH URL |
| `terraform/agentic-ops` | `cf_api_url`, `cf_org_name` | The same as for the platform engineer |

### State backend

`backend.tf` in each root holds the Gitea address, the Gitea organization
`the-goad`, the state name, and the Gitea user `goad-terraform`. For
another Gitea, or another backend, see
[terraform-state.md](terraform-state.md).

## GitOps

The manifests in `gitops/` do not set namespaces or database addresses.
The names below are the exceptions.

| What | Files |
|---|---|
| The DNS domain `goad.gpu.set.lab`: the shop, Zammad, Grafana, Prometheus, and the Gateway's wildcard certificate | `gitops/music-store-apps/gateway-metal-store.yaml`, `httproute-metal-store-frontend.yaml`; `gitops/music-store-platform/gateway-cert.yaml`, `prometheus-agent.yml`; `gitops/platform-tools-apps/zammad.yaml`, `grafana.yaml`, `prometheus.yaml`, `external-secrets.yaml` |
| The probe targets of Prometheus: VCF Automation, VCF Operations, NSX, vCenter, Tanzu Platform, AgentMinder, and addresses of lab services | `gitops/platform-tools-apps/prometheus.yml` |
| The topology panel's names of the lab's systems | `gitops/platform-tools-apps/topology/module.js` |
| The shop's address in the pen test board | `gitops/platform-tools-apps/dashboards/pen-test.json` |

The Avi Service Engine Group is `goad-se-group`, made by
`terraform/cloud-admin/org-config`. How host names are published through
Avi DNS is in [gitops/README.md](../gitops/README.md#host-names).

## Incident apps

`tanzu/metal-music-app-agentic-system/manifest.yml` holds the apps'
routes, under `apps.goad.gpu.set.lab`, and the addresses they call:

- `K8S_API_SERVER`: the `music-store` cluster's API server.
- `AVI_CONTROLLER`: the Avi Controller.
- `QWEN_BASE_URL`: the Private AI Services endpoint, by its name
  `pais.goad.gpu.set.lab` (`gitops/private-ai/ingress.yaml`).
- AgentMinder and Grafana, under `goad.gpu.set.lab`.

`scripts/incident-walk.py` uses the domain for the tickets' customer.

## GitHub

The repository is `modern-apps-5/the-goad`. In a fork, change:

- `gitops_repo` in `terraform/platform-engineer`, and the deploy key in
  [build.md](build.md) step 2.
- `github_url` and `github_app_id` in `terraform/runner`, and the GitHub
  App: see [terraform/runner/README.md](../terraform/runner/README.md).
- `REPO` in `scripts/music-store-build-kubeconfig.sh`, `scripts/goad-ca.sh` and
  `demos/lib/github.sh`, and `ORG` in `scripts/create-github-app.py`.
- The Tanzu Platform API address in `.github/actions/cf-login/action.yml`
  and `.github/actions/cf-token/action.yml`.

The incident apps need Broadcom's AgentMinder Python SDK, which is not on
public PyPI. The workflow `tanzu-apps` pulls it from the private package
`ghcr.io/modern-apps-5/agentminder-sdk`. In a fork, download the SDK from
Broadcom, put it in your own organization with
`scripts/mirror-agentminder-sdk.sh`, and change `SDK_IMAGE` in
`.github/workflows/tanzu-apps.yml` and `IMAGE` in that script.

## Directory

`terraform/cloud-admin/org-config` imports the AD group
`ans-platform-engineer@set.lab` and the AD service account
`svc.platform_engineer@set.lab` from VCF SSO. Make the same two in your
directory, and set their names in its `lab.auto.tfvars`.
