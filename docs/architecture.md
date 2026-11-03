# Architecture

What runs where, and the order the automation builds it in.

## What runs where

The music-store application, manifests and source, is in
[gitops/music-store-apps](../gitops/music-store-apps). The developer
writes the application code in [apps/music-store](../apps/music-store). The
developer does not build or deploy it. The platform engineer builds the
images with Tekton on the platform tools cluster. The platform engineer deploys all of the music store with Argo CD:
the VKS cluster `music-store`, the catalog database, the users VM, and
the containers on that cluster (decision 45).

[gitops/music-store](../gitops/music-store) is the DSM catalog, the VKS
cluster `music-store`, and the users VM. A Job writes the VM's address
and the catalog's address into Endpoints in the VKS cluster. No file
sets a namespace or an address. Terraform creates the `music-store`
namespace with the others, and Argo CD syncs that directory into it. The catalog Service is
`postgres-service`, which is the `DB_HOST` the containers already use.

[gitops/music-store-apps](../gitops/music-store-apps) is the application
and its deploy. It goes into the namespace `music-store` of the VKS
cluster. It is the store, cart, orders, and chat, from the images the
platform engineer builds from `apps/music-store/`. The platform engineer
owns the build and the deploy, and the developer owns
`apps/music-store/`. The catalog password and the chat's model key are not in git.
They are GitHub secrets, which the platform engineer Terraform writes
into Secret Store; ESO in the cluster makes the Secrets `store-db` and
`metal-oracle-model` from them (decision 38).

[gitops/music-store-platform](../gitops/music-store-platform) is the platform
engineer's part inside the VKS cluster: the `ClusterSecretStore` that ESO
reads Secret Store with, the self-signed wildcard certificate for the
shop's Gateway (decision 43), and the Prometheus agent and service account
the platform tools cluster uses to watch the shop.

The shop is published at `music.goad.gpu.set.lab` through Gateway API: the
Gateway `metal-store`, the HTTPRoute `metal-store-frontend`, and the
L7Rule `metal-store-waf`, which puts Avi's WAF policy on the route.

The incident demo's tools run on their own VKS cluster, `platform-tools`,
apart from the cluster they watch (decision 42).
[gitops/platform-tools](../gitops/platform-tools) is the cluster, and
[gitops/platform-tools-apps](../gitops/platform-tools-apps) is Zammad,
Grafana, Prometheus and the blackbox exporter in it. The incident apps
themselves are Cloud Foundry apps in
[tanzu/metal-music-app-agentic-system](../tanzu/metal-music-app-agentic-system),
and `scripts/incident-walk.sh` starts a walk.

## Automation flow

Five Terraform roots, from a machine or from GitHub, then Argo CD and the
`tanzu-apps` workflow. An arrow means the first box is done before the
second one starts.

```mermaid
flowchart TD
    subgraph cloud_admin["1. Cloud admin: terraform/cloud-admin/org"]
        org["Org goad and its local user cloud-admin"]
        sso["VCF SSO: OIDC client in the Identity Broker"]
        quota["Region quota: zone, VM classes, storage"]
        networking["Org networking and regional networking"]
        avi_setting["Avi load balancer setting"]
        dsm_policy["DSM PostgreSQL policy"]
        org --> sso
        org --> quota --> networking --> avi_setting
        org --> dsm_policy
    end

    subgraph org_config["2. Cloud admin: terraform/cloud-admin/org-config"]
        users["VCF SSO users, roles, and project admin"]
        seg["Service Engine Group"]
        am_cluster["Project cloud-admin, namespace agentminder, VKS cluster agentminder"]
        seg --> am_cluster
    end

    subgraph agentminder["3. Cloud admin: terraform/cloud-admin/agentminder"]
        am_helm["Helm: ingress-nginx, infra-ssp, ssp"]
    end

    subgraph platform_engineer["4. Platform engineer: terraform/platform-engineer"]
        namespaces["Supervisor Namespaces: platform, private-ai, music-store, platform-tools"]
        argocd["Argo CD instance, in platform"]
        role["Role for the Argo CD service account"]
        repo_secret["Repository Secret, with the deploy key"]
        pais_secret["Secret pais-static-credentials, in private-ai"]
        kv_secrets["KeyValueSecrets in Secret Store, in music-store and platform-tools"]
        handoff["Per namespace: ManagedEntity, then Application"]
        dev_handoff["For the shop cluster: ManagedEntity music-store-cluster, then Applications music-store-platform and music-store-apps"]
        tools_handoff["For the tools: ManagedEntity platform-tools-cluster, then Applications platform-tools-apps and platform-tools-builds"]
        images["Content library goad-images, with the Ubuntu image"]
        cf_space["Tanzu Platform: space metal-music-app-agentic-system, goad-qwen and k8s-mcp-cluster"]
        namespaces --> argocd --> role --> handoff --> dev_handoff
        handoff --> tools_handoff
        namespaces --> repo_secret
        namespaces --> pais_secret
        namespaces --> kv_secrets
        namespaces --> images
    end

    subgraph registration["5. Agentic ops engineer: terraform/agentic-ops"]
        am_objects["AgentMinder MCP servers, clients, and policies"]
        am_services["User-provided services am-* and sc-*, in the incident apps' space"]
        am_objects --> am_services
    end

    subgraph tanzu_apps["6. Workflow tanzu-apps: tanzu/metal-music-app-agentic-system"]
        incident_apps["The nine incident apps, cf push, then network policies"]
    end

    git[("GitHub: gitops/ on main")]

    subgraph private_ai["Argo CD: gitops/private-ai"]
        pais_wave0["Wave 0: PostgresCluster pais-db and its Service"]
        pais_wave1["Wave 1: Job writes the database address into the Service"]
        pais_wave2["Wave 2: PAISConfiguration"]
        pais_wave3["Wave 3: ModelEndpoint qwen-14b-xlarge"]
        pais_wave0 --> pais_wave1 --> pais_wave2 --> pais_wave3
    end

    subgraph music_store["Argo CD: gitops/music-store"]
        shop_wave0["Wave 0: PostgresCluster catalog, its Service, the VKS cluster music-store, its ESO and cert-manager addons, and the users VM and its Service"]
        shop_wave1["Wave 1: Job writes the database address into the Service"]
        shop_wave2["Wave 2: Job catalog-init fills the catalog, with the password from Secret Store"]
        shop_wave3["Wave 3: Job shop-endpoints writes users-service and postgres-service Endpoints into the VKS cluster"]
        shop_wave0 --> shop_wave1 --> shop_wave2 --> shop_wave3
    end

    subgraph music_store_platform["Argo CD: gitops/music-store-platform"]
        shop_platform["In the VKS cluster: ClusterSecretStore, Gateway certificate, Prometheus agent, blackbox exporter, service account goad-k8s-mcp"]
    end

    subgraph music_store_apps["Argo CD: gitops/music-store-apps"]
        shop_apps["The shop's containers, ExternalSecrets, and Gateway, HTTPRoute and WAF L7Rule, in the VKS cluster"]
    end

    subgraph platform_tools["Argo CD: gitops/platform-tools"]
        tools_cluster["The VKS cluster platform-tools and its ESO addon"]
    end

    subgraph platform_tools_apps["Argo CD: gitops/platform-tools-apps"]
        tools_apps["Zammad, Grafana, Prometheus and the blackbox exporter, in namespace incident-tools"]
    end

    subgraph platform_tools_builds["Argo CD: gitops/platform-tools-builds"]
        tools_builds["Tekton pipeline for the music store's images, in namespace music-store-builds"]
    end

    cloud_admin --> org_config
    org_config -->|"cluster agentminder"| agentminder
    org_config -->|"Service Engine Group, and the svc.platform_engineer API token"| platform_engineer
    repo_secret -.->|"read access"| git
    git -.->|"Argo CD pulls"| handoff
    handoff -->|"Application private-ai"| private_ai
    handoff -->|"Application music-store"| music_store
    dev_handoff -->|"Application music-store-platform"| music_store_platform
    dev_handoff -->|"Application music-store-apps"| music_store_apps
    music_store -.->|"the cluster and the catalog"| music_store_apps
    music_store -.->|"the cluster and its addons"| music_store_platform
    music_store_platform -.->|"ClusterSecretStore and certificate"| music_store_apps
    handoff -->|"Application platform-tools"| platform_tools
    tools_handoff -->|"Application platform-tools-apps"| platform_tools_apps
    tools_handoff -->|"Application platform-tools-builds"| platform_tools_builds
    platform_tools -.->|"the cluster"| platform_tools_apps
    pais_secret -.->|"login for admin"| pais_wave2
    kv_secrets -.->|"passwords and keys"| shop_wave2
    kv_secrets -.->|"passwords and keys, through ESO"| platform_tools_apps
    images -.->|"image for the users VM"| shop_wave0
    agentminder -->|"AgentMinder running"| registration
    cf_space -->|"the space"| registration
    cf_space -->|"space, goad-qwen and k8s-mcp-cluster"| tanzu_apps
    am_services -->|"am-* and sc-* services"| tanzu_apps
```

Solid arrows are that order. Dotted arrows are what one part reads from
another. After the handoff, Terraform does not touch what runs in
`private-ai`, `music-store`, `platform-tools`, and the clusters
`music-store` and `platform-tools`: a commit to `gitops/` on `main` is the
change.

`terraform/agentic-ops` needs the space that the platform engineer makes
and the AgentMinder that the cloud admin installs, so it runs after both.
