# Platform engineer: the platform, from the UI

A five-minute walk through the screens, told by the platform engineer.
No terminal on camera. The platform engineer's work is code: Terraform in
`terraform/platform-engineer` and the manifests in `gitops/`, applied by a
GitHub workflow and Argo CD. This demo is the other side of that code:
what it built, where to see it, and why it helps the people who use it.

The story in one line: I describe the platform once, in git, and VCF
builds it and keeps it that way. App teams get Kubernetes clusters,
databases, VMs and a private AI model without a ticket, and without
knowing how any of it is wired.

Write the video so it works with the sound off. Each step has a caption
for the screen, so another presenter can talk over it, or nobody at all.
The steps do not depend on the rest of the GOAD story, and they need no
other persona on camera.

## The shape of the video

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. Everything is green | Argo CD, Applications |
| 0:20 | 2. The platform is code | GitHub |
| 0:50 | 3. My namespaces, inside the cloud admin's limits | VCF Automation |
| 1:30 | 4. Argo CD is a service, not a project | VCF Automation, then Argo CD login |
| 2:10 | 5. One Application, a whole environment | Argo CD, `music-store` |
| 3:00 | 6. Clusters, a VM and a database, from one API | VCF Automation, namespace `music-store-<suffix>` |
| 3:50 | 7. A private model for the app teams | VCF Automation, namespace `private-ai-<suffix>` |
| 4:15 | 8. The app on top | Argo CD `music-store-apps`, then the shop |
| 4:45 | 9. What I did not do | Argo CD, Applications |

About 30 to 45 seconds a step. Step 9 has an optional self-heal shot
that adds a minute.

## Before the demo

### What you need

- A browser on a machine on the lab network that resolves
  `*.goad.gpu.set.lab`.
- A VCF Automation user in the org `goad` who is in the platform
  engineers' group, `ans-platform-engineer@set.lab`. That group is admin
  in Argo CD and in the project that holds the namespaces. Log in as
  yourself, not as a service account, so the screens show a person.
- Read access to the GitHub repository `modern-apps-5/the-goad`.
- For step 4, the Argo CD address. Ask a teammate, or find it once with
  the `vcf` CLI and `kubectl`, as in the next section.

### Find the Argo CD address

Argo CD has a load balancer address and no host name. Find it from a
vcf context for the platform engineer's namespace, `platform-<suffix>`,
made with your own login:

```bash
vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
  --tenant-name goad --api-token <your API token>
vcf context list | grep ':platform-'      # pick platform-<suffix>, not platform-tools-<suffix>
kubectl --context <that context> get svc argocd-server \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}{"\n"}'
```

Open `https://<that address>` once and accept its certificate before you
record, so the warning page is not in the video.

### Check the lab

Log in to Argo CD with "VCF Automation". Every Application must be
Synced and Healthy:

| Application | What it deploys |
|---|---|
| `private-ai` | A DSM database, Private AI Services, and the Qwen model |
| `music-store` | The VKS cluster `music-store`, the DSM database `catalog`, the users VM `music-users` |
| `music-store-platform` | The platform's part inside that cluster: secrets, certificate, monitoring agents, default deny |
| `music-store-apps` | The shop's containers |
| `platform-tools` | The VKS cluster `platform-tools` |
| `platform-tools-apps` | Grafana, Prometheus and Zammad in that cluster |
| `platform-tools-builds` | The Tekton pipeline that builds the shop's images |

If one is OutOfSync or Degraded, fix it or ask whoever owns it before
you record. See Troubleshooting.

### Set up the browser

Open these tabs, in this order, logged in:

1. Argo CD, Applications, tile view.
2. GitHub: `modern-apps-5/the-goad`, the folder `gitops/`.
3. GitHub: Actions, the latest green run of the `platform-engineer`
   workflow.
4. VCF Automation, `https://auto.gpu.set.lab`, org `goad`.
5. The shop, `https://music.goad.gpu.set.lab`.

Zoom the browser to 125%, hide the bookmarks bar, and close other tabs.

The VCF Automation menu names below are as of 2026-11. Do one dry run
before you record and fix any label that moved.

## Run the demo

Each step has:

- **Go to**: the screen and the clicks.
- **Show**: what to point at, slowly, so it reads with no sound.
- **Say**: the platform engineer's line, first person. Reword it freely.
- **Why it matters**: who it helps. Say it, or keep it for questions.
- **Caption**: the text on screen if the video is played muted.

### 1. Everything is green (0:00)

**Go to**: tab 1, Argo CD, Applications.

**Show**: the seven tiles, all Synced and Healthy. Hover over one to show
its repository path under `gitops/`.

**Say**: "I'm the platform engineer. Everything on this screen is a
Kubernetes cluster, a database, a VM, an AI model or an app that runs on
them. I didn't click any of it into existence. Let me show you where it
came from, and who it's for."

**Why it matters**: sets the promise of the video: a full platform,
running, with one view of its state.

**Caption**: *The whole platform, deployed and healthy, from one view.*

### 2. The platform is code (0:20)

**Go to**: tab 2, `gitops/` in GitHub. Open `music-store/` and click
`cluster.yaml`. Then tab 3, the `platform-engineer` workflow run.

**Show**: in `cluster.yaml`, the cluster's Kubernetes version and its
node pool with `replicas: 2`. Then the green workflow run and its
`terraform apply` step.

**Say**: "This is my job, and it's all in git. A VKS cluster is twenty
lines of YAML: a version, a VM class, a number of workers. The
foundation, the namespaces and Argo CD, is Terraform, and a GitHub
workflow applies it. Any change to the platform is a pull request. My
team reviews it, and git keeps the history."

**Why it matters**: the platform is reviewed, repeatable and auditable.
A second environment is a copy of a folder, not a week of clicks.

**Caption**: *Platform changes are pull requests: reviewed, versioned,
repeatable.*

### 3. My namespaces, inside the cloud admin's limits (0:50)

**Go to**: tab 4, VCF Automation. Build & Deploy, the default project,
Supervisor Namespaces.

**Show**: the four namespaces: `platform`, `private-ai`, `music-store`,
`platform-tools`, each with a generated suffix. Open one and show its
resource limits and its VM classes and storage classes.

**Say**: "The cloud admin gave my team a project with a budget: how much
CPU, memory and storage, which VM sizes, which network. Inside that, I
self-serve. My Terraform made these four namespaces, one for each job:
Argo CD, private AI, the music store, and our tools. I never open a
ticket for infrastructure, and I can't overspend what the cloud admin
set."

**Why it matters**: the cloud admin keeps control of capacity and
networking. The platform team moves at its own speed inside it. Neither
waits on the other.

**Caption**: *Self-service namespaces, inside limits the cloud admin
sets.*

### 4. Argo CD is a service, not a project (1:30)

**Go to**: VCF Automation, namespace `platform-<suffix>`. Show the Argo
CD instance. Then tab 1, log out of Argo CD, and log in again with "VCF
Automation".

**Show**: the instance and its Ready state. On the Argo CD login page,
the "VCF Automation" button, then the same user landing in Argo CD.

**Say**: "Argo CD comes with VCF as a Supervisor Service. I asked for an
instance in one small manifest. I don't install it, patch it or build a
login for it. It signs me in with the same identity as VCF Automation,
and my AD group decides that I'm an admin here."

**Why it matters**: no GitOps tool to run on the side. Access follows
the company directory, so leavers lose it and joiners get it without a
change in Argo CD.

**Caption**: *GitOps as a built-in service, with single sign-on.*

### 5. One Application, a whole environment (2:10)

**Go to**: Argo CD, open the Application `music-store`. Tree view.

**Show**: the tree, left to right: the VKS `Cluster` `music-store`, the
`PostgresCluster` `catalog`, the `VirtualMachine` `music-users`, and the
cluster's addons. Click the `Cluster` and show its live state. Point at
the sync waves: the database and the cluster first, the Job that wires
them together last.

**Say**: "This one Application is a whole environment for the shop: a
Kubernetes cluster, a Postgres database and a VM for the users service.
They're all Kubernetes resources, so Argo CD deploys them in order and
watches them. If someone changes one by hand, Argo CD puts it back to
what git says."

**Why it matters**: the environment is one unit. It can be rebuilt,
copied for a new team, or checked for drift at a glance.

**Caption**: *Cluster, database and VM: one Application, from git, kept
in sync.*

### 6. Clusters, a VM and a database, from one API (3:00)

**Go to**: VCF Automation, namespace `music-store-<suffix>`. Open, in
turn, the Kubernetes clusters, the virtual machines, and the databases.

**Show**:

- The VKS cluster `music-store`: its version, its control plane and two
  workers, Ready.
- The VM `music-users`: running, its VM class, its IP.
- The DSM database `catalog`: PostgreSQL, Ready.

**Say**: "Here's the same thing from VCF's side. The cluster, the VM and
the database are real, and VCF looks after them: it patches the cluster,
it backs up and upgrades the database with Data Services Manager. The
users service still runs on a VM, and that's fine. It sits next to the
containers and Argo CD deploys it the same way."

**Why it matters**: the developer gets a database and a cluster without
waiting on a DBA or a VM team. Ops gets the lifecycle of each one,
managed. VMs and containers are deployed and secured the same way.

**Caption**: *Kubernetes, VMs and managed databases, side by side, one
way to deploy them.*

### 7. A private model for the app teams (3:50)

**Go to**: VCF Automation, namespace `private-ai-<suffix>`. Open Private
AI Services, then the model endpoint. Or, in Argo CD, the Application
`private-ai`, tree view.

**Show**: the model `qwen-14b-xlarge`, Ready, and its database
`pais-db`. In Argo CD, the four waves: database, address, Private AI
Services, model.

**Say**: "The app teams want AI. I give them a model that runs in our own
data center, behind an endpoint they can call. It's the same pattern:
three manifests in git, and Argo CD brings up the database, the service
and the model in order. No data goes to a public model."

**Why it matters**: developers build AI features against an approved
private model. Security and compliance keep the data in house.

**Caption**: *A private AI model, deployed the same way as everything
else.*

### 8. The app on top (4:15)

**Go to**: Argo CD, the Application `music-store-apps`, tree view. Then
tab 5, the shop.

**Show**: in Argo CD, the shop's Deployments and their pods, all Healthy,
and the Gateway and HTTPRoute. In the shop, browse the catalog and open
the chat.

**Say**: "And this is why the platform exists. The developers write the
shop's code. We build their images and deploy them onto the cluster,
and they get a database, a users service, a model for the chat, a
certificate and a web firewall in front. They didn't have to ask for any
of it one piece at a time."

**Why it matters**: the developer's path to production is a commit.
Everything under the app is ready, and the same every time.

**Caption**: *Developers ship code. The platform provides the rest.*

### 9. What I did not do (4:45)

**Go to**: Argo CD, Applications, tile view.

**Show**: the green tiles again.

**Say**: "I didn't log in to vCenter, file a ticket, or install a tool on
the side. I wrote down what the platform should be, and VCF built it and
keeps it that way. When the next team needs one, it's a pull request."

**Caption**: *Describe it once. VCF builds it, and keeps it that way.*

#### Optional: self-heal (+1:00)

In `music-store-apps`, open a Deployment of the shop, pick one of its
pods, and Delete it. The tree shows it Terminating, and a new pod comes
up Healthy within seconds. Say: "Even when something goes away, the
platform puts it back." Do not delete the `Cluster`, the database, or
the VM: Argo CD would rebuild them, but it takes far longer than a demo.

## After the demo

The walkthrough changes nothing, except the optional pod delete, which
Kubernetes replaces. Check that every Application in Argo CD is Synced
and Healthy.

If you clicked Sync, Refresh, or a button in VCF Automation by mistake,
check that Application in Argo CD. Argo CD puts back what git says
within a few minutes.

## Troubleshooting

- **The Argo CD page shows a certificate warning**: the instance has a
  self-signed certificate. Accept it before you record.
- **"VCF Automation" login on Argo CD lands as read only**: your user is
  not in `ans-platform-engineer@set.lab`, or your VCF Automation session
  is from another org. Log out of both and log in to org `goad` again.
- **An Application is OutOfSync**: click it, then App Diff, to see what
  differs. If git changed since the last sync, Sync it, or ask its owner
  first. Record only when it is Synced again.
- **An Application is Progressing for a long time**: a cluster or a
  database is still being built. Open the resource in the tree; its
  message says what it waits on.
- **A namespace is missing in VCF Automation**: you are in another
  project or org. The namespaces are in the org `goad`, default project.
- **The shop does not load**: check that `music.goad.gpu.set.lab`
  resolves on your machine. If it does, check the Application
  `music-store-apps` in Argo CD.
