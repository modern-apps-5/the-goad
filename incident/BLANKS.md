target: Goad org + Goad repo; nothing in Acme

Approved 2026-10-14. `GOAD_VCFA_SPACE` stays empty. The runtime is VKS, recorded in `README.md`. Do not fill a Cloud Foundry space to make `push.py` run.

# Blanks

Every secret, token, password, and host from the source lab is a blank. Org is the literal `Goad`. The space is blank until the Captain names it. Do not put real values in git. Example values below are shapes, not this lab.

| Blank | What it is | Where it is used | Example |
|---|---|---|---|
| `GOAD_VCFA_SPACE` | Tanzu space inside org Goad. Intentionally empty in `manifests/target.yml`. | `manifests/tanzu/push.py`, `pii-scrub/push.sh`, `pii-scrub/chatguard/push.sh`, manifests that name a space | (leave blank until PLAN.md is approved) |
| `TANZU_APPS_DOMAIN` | Apps domain for routes | Agent, door, and pii-scrub manifests and routes | `apps.example.lab` |
| `TANZU_API_HOST` | Platform API host | Docs and any API URL that survived from the source lab | `api.sys.example.lab` |
| `AGENTMINDER_HOST` | AgentMinder issuer host | Sidecar issuer, grant gateway base, door env `IDSP_ISSUER` | `agentminder.example.lab` |
| `AGENTMINDER_GATEWAY_AVI` | AgentMinder gateway URL for the Avi door | `manifests/agentminder/grants.yaml` | `https://agentminder.example.lab/default/aigateway/v1/mcp/<resource-id>` |
| `AGENTMINDER_GATEWAY_K8S` | AgentMinder gateway URL for the Kubernetes door | `manifests/agentminder/grants.yaml` | same shape as the Avi gateway |
| `AGENTMINDER_GATEWAY_VCF` | AgentMinder gateway URL for the VCF door | `manifests/agentminder/grants.yaml` | same shape as the Avi gateway |
| `AGENTMINDER_MCP_HOST` | AgentMinder MCP host, if the estate has a separate one | Docs | `am-mcp.example.lab` |
| `STORE_HOST` | Metal Music Store URL host | `topology/metal-music.json`, `.env.example` | `store.example.lab` |
| `ZAMMAD_HOST` | Helpdesk host | `zammad/cluster/zammad.yaml` and `ZAMMAD_URL` | `zammad.example.lab` |
| `GRAFANA_HOST` | Grafana host | `manifests/grafana/captain-demo-ready.json` link | `grafana.example.lab` |
| `GRAFANA_DATASOURCE_UID` | Infinity datasource uid the boards read | Both Grafana board JSON files, if you replace `company-watch` | `infinity` |
| `KIBANA_HOST` | Log UI host, only if a doc still names it | Docs | `kibana.example.lab` |
| `AVI_CONTROLLER_HOST` | Avi / NSX ALB controller DNS | `manifests/tanzu/push.py`, Avi door env | `avi-ctrl.example.lab` |
| `AVI_CONTROLLER_IP` | Avi controller address | Docs and any inventory note | `203.0.113.10` |
| `AVI_CLUSTER_HOST` | Avi cluster DNS | Docs | `avi-cluster.example.lab` |
| `AVI_CLUSTER_IP` | Avi cluster address | Docs | `203.0.113.11` |
| `AVI_PASSWORD` | Avi / NSX ALB login password. Not in git. `push.py` reads it from the secret store at push time. | Avi door env | (secret store) |
| `VCF_OPS_HOST` | VCF Operations host | `mcp/vcf/hosts.example.json` copy you fill as `hosts.json` (gitignored) | `vcf-ops.example.lab` |
| `VCF_MGMT_HOST` | VCF management host | Docs | `vcf-mgmt.example.lab` |
| `SDDC_MANAGER_HOST` | SDDC Manager host | Avi door login notes, `avi-mcp/.env.example` | `sddc.example.lab` |
| `VCENTER_HOST` | vCenter host | VCF hosts file | `vcenter.example.lab` |
| `NSX_HOST` | NSX manager host | VCF hosts file | `nsx.example.lab` |
| `NSX_VIP_HOST` | NSX VIP host | VCF hosts file | `nsx-vip.example.lab` |
| `ESXI_11_HOST` | ESXi host name | Docs, if present | `esxi-11.example.lab` |
| `ESXI_12_HOST` | ESXi host name | Docs, if present | `esxi-12.example.lab` |
| `ESXI_13_HOST` | ESXi host name | Docs, if present | `esxi-13.example.lab` |
| `ESXI_14_HOST` | ESXi host name | Docs, if present | `esxi-14.example.lab` |
| `VSPHERE_SSO_DOMAIN` | vSphere SSO domain | `avi-mcp/.env.example` | `vsphere.local` |
| `VKS_API_IP` | Guest cluster API address | Docs | `203.0.113.20` |
| `K8S_NODE_A` | Store worker VM name | `topology/metal-music.json` | a VM name from the Goad inventory |
| `K8S_NODE_B` | Store worker VM name. Also the only node the storage-load pod may use. | `topology/metal-music.json`, `fault-injection/storage_load.py`, `mcp/k8s/k8s_mcp.py` | a VM name from the Goad inventory |
| `K8S_NODE_C` | Store worker VM name | `topology/metal-music.json` | a VM name from the Goad inventory |
| `K8S_NODE_CP` | Control plane VM name | `topology/metal-music.json` | a VM name from the Goad inventory |
| `K8S_NODE_A_IP` | Address of `K8S_NODE_A` | `topology/metal-music.json` | `203.0.113.21` |
| `K8S_NODE_B_IP` | Address of `K8S_NODE_B` | `topology/metal-music.json` | `203.0.113.22` |
| `K8S_NODE_C_IP` | Address of `K8S_NODE_C` | `topology/metal-music.json` | `203.0.113.23` |
| `VSAN_DATASTORE` | Datastore the store VMs share | `topology/metal-music.json`, `fault-injection/storage_load.py` | the datastore name from inventory |
| `STORE_POD_IP` | An example pod address in a readiness message | Docs, if present | `203.0.113.30` |
| `DIEGO_CELL_IP` | Platform cell address, source-lab only | Docs, if present | `203.0.113.40` |
| `LAB_NET_172_16_15_128` | Source-lab address, fill only if a doc still names it | Docs | `203.0.113.41` |
| `LAB_NET_192_168_2_29` | Source-lab address, fill only if a doc still names it | Docs | `203.0.113.42` |
| `COMMAND_BOX_HOST` | Orchestrator machine DNS | Docs | `orchestrator.example.lab` |
| `COMMAND_BOX_IP` | Orchestrator machine address | Docs | `203.0.113.50` |
| `OBSERVER_HOST` | Grafana or observer DNS | Board link | `grafana.example.lab` |
| `OBSERVER_IP` | Observer address | Docs | `203.0.113.51` |
| `SPARK_HOST` | House model host | Docs, model endpoint | `model.example.lab` |
| `SPARK_IP` | House model address | Docs | `203.0.113.52` |
| `JEV_BASE_URL` | Jev root URL. Not committed. | env file read by `orchestrator/jev.py` | `https://api.example.invalid` |
| `JEV_API_KEY` | Jev bearer key. Not committed. | env file | (secret store) |
| `ZAMMAD_URL` | Helpdesk base URL | env file, `demo.sh` clients | `https://zammad.example.lab` |
| `ZAMMAD_TOKEN` | Helpdesk API token. Not committed. | env file | (secret store) |
| `ZAMMAD_USER` | Helpdesk user. Not committed. | env file | `agent@example.lab` |
| `ZAMMAD_PASSWORD` | Helpdesk password. Not committed. | env file | (secret store) |
| `ZAMMAD_DB_PASSWORD` | Database password if you install the bundled helpdesk manifest. The published compose default was removed. | `zammad/cluster/zammad.yaml` | (secret store) |
| `DGX_BASE_URL` | House model URL used by the orchestrator | env file | `https://model.example.lab/v1` |
| `DGX_API_KEY` | House model key, if the endpoint requires one. Not committed. | env file | (secret store) |
| `MCP_READ_TOKEN` | Read bearer for a door. Not committed. | door env, set by `push.py` from the secret store | (secret store) |
| `MCP_WRITE_TOKEN` | Write bearer for a door. Not committed. | door env | (secret store) |
| `MCP_TOKEN` | Bearer for the incident-live app. Not committed. | `push.py` writes it to the secret store, not to git | (secret store) |
| `AGENTMINDER_CLIENT_ID` | OAuth client id for an agent sidecar. Not committed. | agent env, set at push | (secret store) |
| `AGENTMINDER_CLIENT_SECRET` | OAuth client secret. Not committed. | agent env, set at push | (secret store) |
| `AGENTMINDER_SIDECAR_TOKEN` | Sidecar token. Not committed. | agent env | (secret store) |
| `LAB_CA_FILE` | Platform CA bundle. Not in git. The droplet path in the manifest is `/home/vcap/app/sidecar/lab-ca.pem`. | agent sidecar TLS | a PEM file outside git |
| `SDDC_PASSWORD` | SDDC or NSX admin password used only if the Avi door must mint a session. Not committed. | Avi door env via `push.py` | (secret store) |
| `K8S_API_SERVER` | Guest cluster API URL | Kubernetes door env | `https://203.0.113.20:6443` |
| `K8S_TOKEN` | Guest cluster token. Not committed. | Kubernetes door env | (secret store) |

`company-watch` in the Grafana JSON is the source board's Infinity datasource uid. Point it at the Goad datasource during assembly (`GRAFANA_DATASOURCE_UID`).

`mcp/vcf/hosts.example.json` uses example hosts. Copy it to `hosts.json` (gitignored) and fill the Goad estate. Do not commit `hosts.json`.
