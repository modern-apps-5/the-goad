# GOAD walkthrough script

Five videos. The theme in the plan is "Declarative Deployment,
Visual Validation."

Videos 2, 3, and 4 are titles only. Video 1 is a sketch, and one
page of Scene 5 is missing. This file is the script as it stands,
not a finished shoot script.

## Where this script differs from what is built

As of 2026-10-28. The lines below are the script as written. They have
not been changed to match. Fix these when Video 1 is rewritten.

- **Scene 2, Cloud Admin.** The script has the cloud admin deploy the
  namespace, bootstrap Argo CD, and create the VKS cluster. As built,
  Argo CD creates the music-store VKS cluster from `gitops/music-store`,
  which is the platform engineer's work. The cloud admin creates the org,
  its quota, its networking, the Avi setting, the DSM policy, the users
  and groups, the Service Engine Group, and AgentMinder on its own VKS
  cluster. The platform engineer creates the namespaces and Argo CD. The
  region is not created by anyone on camera; it exists already.
- **Scene 2, Platform Engineer.** Argo CD does deploy the DSM database.
  It also deploys Private AI Services and the model, which the script
  does not mention, and a second VKS cluster, `platform-tools`, for
  Zammad, Grafana and Prometheus. AKO is part of VCF and is not deployed
  by Argo CD.
- **Scene 2, Developer.** The shop's chat is a container on VKS, not a
  chatbot on Tanzu. What runs on Tanzu Platform is the incident demo's
  agents and MCP servers, behind AgentMinder. The model is Qwen in
  Private AI Services.
- **Scene 3, Cloud Admin.** The namespace shown is the platform
  engineer's work, not the cloud admin's. No GPU is allocated, so "GPU
  tenancy" cannot be said.
- **Scene 4.** Of the security admin's part, only Avi's WAF on the shop's
  route is built (decision 43), and AgentMinder's policies on the
  incident agents' tools.

The commands that exist today are the Terraform roots (cloud admin, then
platform engineer, from a machine or the GitHub workflows), `git push`
for what Argo CD syncs, and `cf push` from the `tanzu-apps` workflow.

## Video 1 — Day 0, instantiation and architecture

**Goal.** Start with the architecture, show the manifests and the
deployment, then walk the resulting UI so the VCF pieces look
connected.

### Scene 1 — Architecture and personas

1. Visual: an architecture diagram of Metal Music Store AI with the
   four personas.
2. Narration: "Welcome to the Grandmother of All Demos. Today we
   are deploying a modern, distributed retail application, the Metal
   Music Store. Our architecture spans multiple environments: a
   cloud-native frontend on Kubernetes (VKS), a legacy Users service
   running on a traditional VM, a backend PostgreSQL database
   managed by VMware Data Services Manager (DSM), and an agentic AI
   chatbot running on Tanzu. Let's meet the personas managing this
   lifecycle."

### Scene 2 — Manifests and deployment

1. Visual: a fast screen share of the manifest files, then the
   deployment terminals.
2. Cloud Admin: "First, we establish the foundation. Using
   Terraform, we deploy the VCF Automation namespace, bootstrap
   Argo CD, and instantiate the base VKS cluster."
3. Security Admin: "Security is defined as code. We use Terraform
   to configure AgentMinder policies, vDefend DFW, and SSP for the
   vSphere VMs. For our containerized workloads, GitOps pushes
   Antrea microsegmentation policies directly to the VKS cluster."
4. Platform Engineer: "Once Argo CD is bootstrapped, it takes over.
   Using YAML manifests sent to the VCF Automation Kubernetes API,
   Argo CD automatically deploys everything into the cluster. It
   triggers the namespace API in VCF Automation to deploy our DSM
   database, uses the VM Service manifest to spin up the Users VM,
   and deploys the Avi Kubernetes Operator (AKO)."
5. Developer: "Finally, for our agentic Metal Oracle chatbot, we
   use a simple application manifest file and execute a cf push
   directly to the Tanzu runtime."
6. Action: terraform apply, commit to the Argo CD repo, cf push.
   Terminals end on successful deployment output.

### Scene 3 — Foundation and platform

1. Cloud Admin, vSphere Client: "Here is the vSphere Namespace
   created by Terraform. It is the strict demarcation line providing
   compute and secure GPU tenancy."
2. Platform Engineer, showing Argo CD: "Argo CD handled the rest.
   You can see all our apps, the VM Service, and DSM are fully
   synced."
3. Platform Engineer, DSM UI: "Here is our Postgres database,
   provisioned entirely through Argo CD calling the VCF Automation
   namespace API."
4. Platform Engineer, vSphere inventory: "And here is our Users VM,
   provisioned via Kubernetes manifests using the VM Service."

### Scene 4 — Securing the stack

1. Security Admin, NSX UI: "Terraform applied our vDefend DFW and
   SSP policies to lock down the Users VM. In the same UI we see
   the Antrea rules that Argo CD pushed."
2. Security Admin, Avi UI: "Notice these virtual services and the
   WAF. We didn't build these manually. AKO automatically translated
   our Kubernetes ingress resources into this configuration."
3. Security Admin, AgentMinder: "Finally, our Terraform scripts
   configured AgentMinder, setting the strict identity groups and
   intents."

### Scene 5 — The app

The source jumps. The first lines are here. A later page starts in
the middle of the store walk. The clicks between them were not in
the photos.

- Developer shows the Tanzu interface. "Our cf push instantly
  containerized and deployed the Metal Oracle agent."
- Developer opens the live storefront. "Let's prove it all works. I
  click Admin Login,"
- The missing page ends mid-sentence: the login "successfully
  routes to our VM Service-backed Users VM. I add an item to the
  cart, which writes seamlessly to our DSM-managed Postgres
  database."
- "Finally, I open the Metal Oracle chat and ask for album
  recommendations. The agent, running on Tanzu, securely
  authenticates via AgentMinder and accesses our inventory context
  to provide a real, intelligent response."

## Video 2 — Day 1, troubleshooting

To be developed.

- Focus: users report latency talking to the Metal Oracle under
  load.
- Actions: Cloud Admin uses VCF Operations. Platform Engineer uses
  Headlamp and Istio to trace latency to pod constraints and load
  balancer capacity.

## Video 3 — Day 2, scaling

To be developed.

- Focus: scale Kubernetes deployments and watch Avi scale service
  engines.
- Actions: Platform Engineer scales the app. Cloud Admin adjusts
  Supervisor resource quotas in VCF Operations.

## Video 4 — Day 3, security incident

To be developed.

- Focus: a simulated attack from the Store frontend toward the
  Users VM or the DSM database.
- Actions: vDefend SSP detects anomalous traffic. Security Admin
  quarantines pods with DFW and Antrea and updates the Avi WAF.
  AgentMinder revokes AI access.

## Video 5 — End-to-end master cut

A cohesive edit of videos 1 through 4. Nothing to write until those
four exist.

## What the script still needs

- Assign each named person to one persona. The developer row in the
  design table is cut off, so the assignment is not decided.
- Videos 2, 3, and 4 need a setup, the thing that breaks, the screen
  that proves it, and the line to say. A focus sentence is not a
  scene.
- Video 1 Scene 2 is six products in one breath. Split it into
  shots that can be filmed on a day when that product is actually
  up. Do not narrate Argo CD, DSM, the VM Service, vDefend, and a
  GPU namespace in one take before they exist.
- Scene 5 needs the missing clicks: admin login, the users VM, the
  cart write, then the Oracle question. Write the question the
  developer asks, and the inventory fact the tool must return.
- The Oracle must not invent an album count. The line should say
  the agent reads the tool result and stops.
- Two bullets disagree about Avi and AgentMinder. One says Avi
  replaces the AgentMinder gateway for model routing. Another says
  Avi is the AgentMinder gateway. The spoken line has to pick one:
  Avi load-balances. AgentMinder decides what the agent may call.
- Do not say "secure GPU tenancy" if the private model is on CPU.
- Video 5 cannot be cut until 2, 3, and 4 have scenes.
