# Cloud admin, stage 3: AgentMinder

The cloud admin's third Terraform root. It installs AgentMinder on the
VKS cluster that [../org-config](../org-config) created. The Helm chart
calls AgentMinder SSP, Security Services Platform. Apply
`terraform/cloud-admin/org` and `terraform/cloud-admin/org-config`
first. The state is `goad-cloud-admin-agentminder`.

It is a separate root because its Helm and Kubernetes providers need the
cluster's address. The address does not exist until `org-config` has
applied. See [decision 29](../../../docs/decisions.md).

| File | What it creates |
|---|---|
| `providers.tf` | Reads the state of `org-config`, gets the cluster's admin kubeconfig, and configures the Helm and Kubernetes providers with it. |
| `agentminder.tf` | The namespace `ssp`, the pull secret, the Helm releases `ingress-nginx`, `infra-ssp`, and `ssp`, and the Service for the second DNS name. |
| `outputs.tf` | `ingress_address` and `agentminder_url`. |

## What it creates

- `ingress-nginx` 4.15.1. Its Service is a LoadBalancer, served by the
  org's Avi Service Engine Group. Snippet annotations are on, because
  AgentMinder's Ingress uses them.
- The namespace `ssp`, with Pod Security `privileged`, like the lab's
  other AgentMinder. A stricter profile has not been tried.
- The Secret `ssp-registry`, a `dockerconfigjson` for
  `securityservices.packages.broadcom.com`. Terraform makes it and both
  charts read it through `existingSecrets`. The password is then in one
  place.
- `infra-ssp`, the chart `ssp-infra` 4.1.1+1673: the Percona MySQL
  database.
- `ssp`, the chart `ssp` 4.1.1+1673: AgentMinder.
- The Service `ingress-nginx-mgmt-dns`: a second LoadBalancer Service on
  the same ingress controller, for the second name
  `mgmt-agentminder.goad.gpu.set.lab`. This AKO build takes one name per
  Service. It was made by hand first and is imported.

The agents and MCP servers are not configured here. The agentic ops
engineer's root, [../../agentic-ops](../../agentic-ops), registers them.
It logs in as AgentMinder's default tenant admin client. After this stage
applies, the cloud admin copies that client's ID and secret once into the
repository secrets `AGENTIC_OPS_AGENTMINDER_CLIENT_ID` and
`AGENTIC_OPS_AGENTMINDER_CLIENT_SECRET`: see
[terraform/runner/README.md](../../runner/README.md).

The charts come from `https://ssp_helm_charts.storage.googleapis.com`.

## Helm values

It is installed small: [decision 30](../../../docs/decisions.md).

On:

- `ssp.deployment.size` is `demo`, one replica of each service.
- Hazelcast has one member.
- `aigateway` and `mcpserver`.
- `dataseed`.
- The database volume is 20Gi.

Off:

- `otelCollector`, `custommetrics`, and `selfserviceconsole`.
- `fluent-bit`, so logs stay in the pods.
- `localLlm`, the local model for the MCP playground. It is off by
  default.
- `global.observe`, the observability pipeline. It is off by default.

## Apply

The remote state of `org-config` is read with the `http` backend. A
data source cannot read `backend.hcl`, so the token must also be in the
environment.

```sh
cp terraform.tfvars.example terraform.tfvars   # secrets only; copy the team's if the demo is built
cp backend.hcl.example backend.hcl             # then put the state token in it
export TF_HTTP_PASSWORD=<the same token>
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

The first install seeds the database before the services start. The
`ssp` release waits up to 30 minutes for it.

## Inputs

- `lab.auto.tfvars`, in git: `vcfa_url`, `allow_unverified_ssl`, and
  `agentminder_hostname`. `org_name` (default `goad`),
  `cloud_admin_username` (default `cloud-admin`), `ssp_chart_version`
  (default `4.1.1+1673`), and `ingress_nginx_chart_version` (default
  `4.15.1`) have defaults.
- `terraform.tfvars`, not in git: `cloud_admin_password`, the same value
  as in `terraform/cloud-admin/org`, and `ssp_registry_username` and
  `ssp_registry_password`, the login for Broadcom's image registry.
  Copy the team's file.

In GitHub the registry login is the repository secrets
`SSP_REGISTRY_USERNAME` and `SSP_REGISTRY_PASSWORD`. The workflow sets
`TF_HTTP_PASSWORD` for you.

## DNS

The hostname is `agentminder.goad.gpu.set.lab`. Nobody adds the record by
hand.

- The ingress controller's Service has `loadBalancerClass:
  ako.vmware.com/avi-lb`, so the cluster's AKO serves it, not the
  Supervisor. AKO serves only Services of that class here
  (`defaultLBController` is `false`).
- The Service has the annotation
  `external-dns.alpha.kubernetes.io/hostname`. AKO puts that name on the
  Avi virtual service.
- Avi DNS is authoritative for `goad.gpu.set.lab`, and the lab DNS
  delegates that zone to it (the `avi-dns` scripts). The record answers
  within a minute.

So the hostname must be in `goad.gpu.set.lab`. A name outside that zone
gets no record.

```sh
terraform output ingress_address
dig +short agentminder.goad.gpu.set.lab   # the same address
```

## Check it

```sh
kubectl -n ssp get pods
kubectl -n ssp logs deploy/ssp-ssp-aigateway -c ssp-aigateway
```

Use the admin kubeconfig of the cluster `agentminder`. All pods in `ssp`
should be `Running` or `Completed`. Then open `agentminder_url`. The
certificate is self-signed.
