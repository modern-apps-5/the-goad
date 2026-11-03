# Platform engineer: the platform, from the UI

A five-minute browser demo, as the platform engineer. Start in VCF
Automation, show what you set up for the music store, how you set it up,
and the app it delivers. No terminal, no changes. The golden path from
a commit to production is its own demo, [golden-path](../golden-path).

The point: the platform engineer lets the developers focus on code. They
own the delivery of that code and consume the infrastructure services it
needs. VCF runs those services.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The cloud console | VCF Automation, Supervisor Namespaces |
| 0:40 | 2. What the music store runs on | VCF Automation, `music-store-<suffix>` |
| 1:20 | 3. A private AI model | VCF Automation, `private-ai-<suffix>` |
| 1:50 | 4. GitOps, from the console | VCF Automation GitOps tab, then Argo CD |
| 2:30 | 5. One Application, a whole environment | Argo CD, `music-store` |
| 3:10 | 6. It's all code | GitHub |
| 3:40 | 7. The app, delivered | Argo CD, `music-store-apps` |
| 4:10 | 8. The app | The shop |
| 4:30 | 9. Back to the console | VCF Automation |

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`. That group is admin in Argo CD and in
  the project that holds the namespaces.
- Read access to the GitHub repository `modern-apps-5/the-goad`.

### Check the lab

1. In VCF Automation, open namespace `platform-<suffix>` (not
   `platform-tools-<suffix>`), the GitOps tab, and click the button on
   the Argo CD instance. Log in with "VCF Automation".
2. Check every Application is Synced and Healthy:

   | Application | What it deploys |
   |---|---|
   | `private-ai` | A DSM database, Private AI Services, and the Qwen model |
   | `music-store` | The VKS cluster `music-store`, the DSM database `catalog`, the users VM `music-users` |
   | `music-store-platform` | The platform's part inside that cluster: secrets, certificate, monitoring agents, default deny |
   | `music-store-apps` | The shop's containers |
   | `platform-tools` | The VKS cluster `platform-tools` |
   | `platform-tools-apps` | Grafana, Prometheus and Zammad in that cluster |
   | `platform-tools-builds` | The Tekton pipeline that builds the shop's images |

   If one is not, see Troubleshooting.
3. Log out of Argo CD, so step 4 shows the login.

### Browser tabs

1. VCF Automation, `https://auto.gpu.set.lab`, org `goad`, Build &
   Deploy, the default project, Supervisor Namespaces.
2. GitHub: `gitops/music-store/cluster.yaml`.
3. GitHub: Actions, latest green run of `platform-engineer`.
4. The shop, `https://music.goad.gpu.set.lab`.

Argo CD opens in its own tab in step 4.

## Run the demo

### 1. The cloud console (0:00)

Tab 1, VCF Automation, Supervisor Namespaces.

**Show**

- The four namespaces: `platform`, `private-ai`, `music-store`,
  `platform-tools`.
- Open one: its resource limits, VM classes and storage classes.

**Why**: the cloud admin sets the budget and the networks. The platform
engineer self-serves inside it, with no tickets.

### 2. What the music store runs on (0:40)

Namespace `music-store-<suffix>`: Kubernetes clusters, virtual machines,
databases.

**Show**

- VKS cluster `music-store`: version, control plane, two workers, Ready.
- VM `music-users`: running, VM class, IP.
- DSM database `catalog`: PostgreSQL, Ready.

**Why**: the developers get a cluster, a database and a VM without
waiting on a DBA or a VM team. VCF patches the cluster; Data Services
Manager backs up and upgrades the database. The platform engineer only
consumes them.

### 3. A private AI model (1:20)

Namespace `private-ai-<suffix>`: Private AI Services, then the model
endpoint.

**Show**

- Model `qwen-14b-xlarge`, Ready.
- Its database `pais-db`.

**Why**: the shop's chat uses a model in our own data center. No data
goes to a public model, and no one runs a model server by hand.

### 4. GitOps, from the console (1:50)

Namespace `platform-<suffix>`, GitOps tab. Click the button on the Argo
CD instance, log in with "VCF Automation".

**Show**

- The Argo CD instance, Ready, and the button that opens it.
- The "VCF Automation" login.
- All tiles Synced and Healthy: everything from steps 2 and 3 is here.

**Why**: none of it was clicked into existence. Argo CD is a VCF
service, not a tool to install and patch, and it signs in with the same
identity as VCF Automation.

### 5. One Application, a whole environment (2:30)

Argo CD, Application `music-store`, tree view.

**Show**

- The `Cluster` `music-store`, the `PostgresCluster` `catalog`, the
  `VirtualMachine` `music-users`, the cluster's addons.
- The `Cluster`'s live state.
- The sync waves: database and cluster first, the Job that wires them
  together last.

**Why**: the environment is one unit, deployed in order and kept in
sync. A hand change is put back to what git says.

### 6. It's all code (3:10)

Tab 2, then tab 3.

**Show**

- `cluster.yaml`: Kubernetes version, node pool with `replicas: 2`.
- The `platform-engineer` workflow run, its `terraform apply` step.

**Why**: the namespaces and Argo CD are Terraform; the clusters,
databases and VMs are YAML. Every platform change is a reviewed pull
request. A second environment is a copy of a folder.

### 7. The app, delivered (3:40)

Argo CD, Application `music-store-apps`, tree view.

**Show**

- The shop's Deployments, pods Healthy.
- The Gateway and HTTPRoute.
- A pod's image: `depot.kube-system.svc/music-store/<service>`, tagged
  with a commit.

**Why**: the developers only write code. The platform engineer's golden
path builds it from trusted sources and deploys it here. The
[golden-path](../golden-path) demo shows it end to end.

### 8. The app (4:10)

Tab 4, the shop.

**Show**: the catalog, then the chat.

**Why**: the developers' app, running on everything above.

### 9. Back to the console (4:30)

Tab 1, Supervisor Namespaces.

**Show**: the four namespaces again.

**Why**: no vCenter login, no tickets, no service run by hand. The next
team is a pull request.

## After the demo

Check every Application in Argo CD is Synced and Healthy. If you clicked
Sync, Refresh or a VCF Automation button by mistake, Argo CD puts back
what git says within a few minutes.

## Troubleshooting

- **"VCF Automation" login on Argo CD lands as read only**: your user is
  not in `ans-platform-engineer@set.lab`, or your VCF Automation session
  is from another org. Log out of both and log in to org `goad` again.
- **An Application is OutOfSync**: click it, then App Diff, to see what
  differs. If git changed since the last sync, Sync it, or ask its owner
  first.
- **An Application is Progressing for a long time**: a cluster or a
  database is still being built. Open the resource in the tree; its
  message says what it waits on.
- **A namespace is missing in VCF Automation**: you are in another
  project or org. The namespaces are in the org `goad`, default project.
- **The shop does not load**: check that `music.goad.gpu.set.lab`
  resolves on your machine. If it does, check the Application
  `music-store-apps` in Argo CD.
