# Goad agentic runbook

How to rebuild the Metal Music incident demo in Red Lab, and the lessons
that cost a wrong turn. No secrets in this file. Fill blanks from
`BLANKS.md` at apply time.

## Lessons

- Agents and MCP servers run on Tanzu Platform (`cf push`), org `Goad`,
  space `metal-music-app-agentic-system`. They are not VKS pods. The
  guest namespace `metal-music-app-agentic-system` was the wrong runtime.
  Do not delete those pods until a second approval, and do not add new
  ones.
- The shop is `gitops/music-store/app`, namespace `music-store` on
  the VKS cluster `music-store`. Argo CD syncs it. This tree has no
  store. Do not deploy `app/music-store`.
- Users are the VM Service VM `music-users` and `users-service`. The
  catalog is the DSM `PostgresCluster` `catalog`. The slow-page fault is
  the view `albums` over `albums_data` (`pg_sleep`). Do not run a
  disk-write loop. Do not replace the catalog with a container Postgres.
- Qwen is the Goad Private AI `ModelEndpoint` `qwen`. 1.5B on
  `best-effort-medium` is too small to call tools. Use the 14B weights
  on `best-effort-xlarge`. Do not bind the GenAI plan
  `chat-and-tools-model` (that plan follows the other organization's
  Private AI). Do not use a DGX model plan.
- Zammad and Grafana share one guest namespace, `incident-tools`, on
  cluster `music-store`.
- The standard Red Lab password is the cloud-admin password. Grafana
  user `admin` and the Zammad admin user get that password in cluster
  secrets only. Never write it into git, a log, or a report.
- AgentMinder console is
  `https://<AGENTMINDER_HOST>/default/ui/v1/adminconsole/`. `/` on the
  product is a Spring 404. The Goad ingress redirects `/` to that path.
- The Avi account on this cluster can sign in and still get HTTP 403 on
  `GET /api/virtualservice`. `avi_latency` records that denial. The note
  still finishes. Do not invent another Avi account.
- The decision gate is CLM. Set `CLM_URL` when a CLM image exists in
  this lab. Blank `CLM_URL` is the fallback, and the enrichment note
  says so. Do not point the gate at a machine outside this lab.
- Never start the VPN. The unit is `openvpn-client@redlab`. The config
  is `/etc/openvpn/client/redlab.conf`. The Captain starts it. If `tun0`
  is down, stop.
- Never use the DGX.
- An idle pod that only serves `/health` is not a working agent. Success
  is the Captain chat on the Tanzu incident response app: the phrase
  `pick up the latest incident ticket and enrich it`, steps in that
  chat and as Grafana annotations, and one Zammad note whose root cause
  is storage latency.
- Keep the lab logs. Reuse the home-lab agent and tool code. Do not
  rewrite the skills.
- This foundation has one Diego cell, about 16 GB, and Diego places by
  reservation, not by RSS. `cf start` fails with `InsufficientResources`
  while the cell still has free RAM. Shrink other apps' reservations
  before staging these nine. The Java app `autoscale-api` needs 1024M;
  512M is below its non-heap budget and the process exits immediately.
- `cf add-network-policy` takes the destination app as a positional
  argument (`SOURCE DESTINATION`), not `--destination-app`.
- `apps.internal` does not answer until `cf map-route APP apps.internal
  --hostname APP` is done for the destination. A network policy alone
  leaves bosh-dns with an empty answer, and the chat reports
  `URLError` in under a second. Map `metal-incident-live` and the three
  diagnostic agents. The chat calls the orchestrator on
  `metal-incident-live.apps.internal:8080`. The orchestrator calls the
  three agents the same way.

## DNS

Avi internal DNS is the authority for `goad.gpu.set.lab`. The IPAM/DNS
profile is `avi-dns-domains` (`IPAMDNS_TYPE_INTERNAL_DNS`). The zone SOA
is `avi-dns.gpu.set.lab`. The name server is `ns1.gpu.set.lab`. The lab
resolver `172.21.0.90` and the Ops Manager forwarder both recurse to it.

Register a name by putting the FQDN on the virtual service that already
owns the VIP. Do not create a static DNS record.

For an `avi-lb` ingress, AKO does that when both of these are set:

- `spec.rules[].host` is the FQDN
- annotation `external-dns.alpha.kubernetes.io/hostname` is the same FQDN
- annotation `ako.vmware.com/service-engine-group` is `goad-se-group`

AKO writes the host onto the child virtual service (`vh_matches.host`).
Avi DNS answers with that virtual service's VIP. The record TTL is 30
seconds. This is how `music`, `incident`, `zammad`, `grafana`,
`k8s-mcp`, `avi-mcp`, and `vcf-mcp` under `goad.gpu.set.lab` are
published.

AgentMinder is a LoadBalancer service in front of nginx, not an
`avi-lb` ingress. Its FQDN is the service annotation
`external-dns.alpha.kubernetes.io/hostname` on
`ingress-nginx/ingress-nginx-controller`. This AKO build stores that
annotation as one domain name. A comma-separated list is rejected by
Avi (`invalid label`). One name per service.

`mgmt-agentminder.goad.gpu.set.lab` is a second hostname on the nginx
ingress. Give it a second LoadBalancer service with the same pod
selector, `spec.loadBalancerClass: ako.vmware.com/avi-lb`,
service-engine group `goad-se-group`, and its own hostname annotation.
The class has to be set at create time. AKO publishes that FQDN on the
new virtual service. A Helm upgrade of `ingress-nginx` does not own
that extra service.

The same DNS profile also holds other organizations' domains. Leave
those domains and their records alone.

`*.apps.tp.gpu.set.lab` is not a domain in that Avi profile. The lab
resolvers already answer every name in that zone, including names that
were never created one by one, with the GoRouter address. Because those
names already resolve, no wildcard was added in Avi.

Check from a client with `dig @172.21.0.90 <name> A`, then HTTP to the
address with the `Host` header set to the name. This machine's stub
resolver does not forward these names. Success is a resolved address
and a page or `/health` that loads, not a record that only exists in
Avi.

## Where each piece runs

| Piece | Where |
|---|---|
| Storefront | VKS `music-store`, namespace `music-store`, path `gitops/music-store/app` |
| Users VM, DSM catalog | supervisor namespace for `music-store` |
| Zammad, Grafana | VKS `music-store`, namespace `incident-tools` |
| Qwen 14B | Goad Private AI `ModelEndpoint` `qwen` |
| Four agents, orchestrator, three MCP servers, pii-scrub | Tanzu org `Goad`, space `metal-music-app-agentic-system` |
| AgentMinder | already in this organization |

Routes, after `cf push`:

- `https://incident-response-agent.${TANZU_APPS_DOMAIN}/` is the chat
- `https://lb-diagnostic-agent.${TANZU_APPS_DOMAIN}/health`
- `https://k8s-diagnostic-agent.${TANZU_APPS_DOMAIN}/health`
- `https://vcf-diagnostic-agent.${TANZU_APPS_DOMAIN}/health`
- `https://metal-k8s-mcp.${TANZU_APPS_DOMAIN}/health`
- `https://metal-avi-mcp.${TANZU_APPS_DOMAIN}/health`
- `https://metal-vcf-mcp.${TANZU_APPS_DOMAIN}/health`
- `https://metal-incident-live.${TANZU_APPS_DOMAIN}/health`
- `https://pii-scrub.${TANZU_APPS_DOMAIN}/health`

Manifests: `tanzu-agents/manifest.yml`, `tanzu-agents/mcp.yml`,
`tanzu-agents/live.yml`, `tanzu-agents/pii.yml`. Push:
`tanzu-agents/push.py`.

## Rebuild order

1. Confirm `systemctl is-active openvpn-client@redlab` is `active` and
   `tun0` has an address. Do not start the unit.
2. Confirm the users VM is PoweredOn and `users-service` `/health` is
   HTTP 200.
3. Confirm DSM `PostgresCluster` `catalog` is Ready, and `albums` is a
   view (`relkind` `v`) over `albums_data` (`relkind` `r`).
4. Confirm Private AI `ModelEndpoint` `qwen` is the 14B endpoint on
   `best-effort-xlarge` and Ready. A one-word completion returns.
5. The shop is already `gitops/music-store/app`. Confirm
   `GET /` on `STORE_HOST` is HTTP 200. This tree does not apply a store.
6. Apply Zammad from `zammad/` and Grafana from `observability/` into
   namespace `incident-tools`. `ZAMMAD_HTTP_TYPE` is `http` because the published
   URL is `http://`. Set Grafana `admin` and the Zammad admin password
   in the cluster secrets to the standard lab password. Do not print it.
7. `cf target -o Goad -s metal-music-app-agentic-system` on
   `https://api.sys.tp.gpu.set.lab`. Create the org and space if they
   are absent. Do not push into org `demo`.
8. `python3 tanzu-agents/push.py` with the blanks in the environment
   (`QWEN_*`, `ZAMMAD_*`, `GRAFANA_*`, `K8S_TOKEN`, Avi controller
   fields). The script does not print them.
9. Point the three AgentMinder resource servers `goad-k8s-mcp`,
   `goad-avi-mcp`, and `goad-vcf-mcp` at
   `https://metal-*-mcp.${TANZU_APPS_DOMAIN}/mcp`.
10. `walk/demo.sh start` slows the catalog and opens one Zammad ticket.
    It does not start the agents.

## Verification

- Each of the nine apps: `GET /health` is HTTP 200.
- `GET /` on the incident response route is the chat page.
- Send `pick up the latest incident ticket and enrich it` in that chat.
- The chat lists the ticket, each diagnostic step, and the line
  `Decision gate: CLM fallback (CLM_URL is unset)` when `CLM_URL` is blank.
- Grafana annotations tagged `incident` gain one row per step.
- The newest Zammad ticket gains one article whose subject is
  `Enrichment` and whose body names storage latency as the root cause.
- `avi_latency` may be denied (HTTP 403). The note still posts.
- Do not claim the walk passed because `/health` was 200.

## What stays after a later pod removal

Only with a second approval, remove the VKS deployments
`incident-response-agent`, `orchestrator`, `lb-diagnostic-agent`,
`k8s-diagnostic-agent`, `vcf-diagnostic-agent`, `pii-scrub`,
`goad-k8s-mcp`, `goad-avi-mcp`, and `goad-vcf-mcp`. Keep the store, the
users VM, the catalog, Zammad, Grafana, Qwen, and AgentMinder.
The incident ingress rule shares a VIP with Zammad. Remove the incident
host rule only.
