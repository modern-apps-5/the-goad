# Execution plan

Suggested order. The design is the target. The script is ahead of
the software. Build one true scene, then write the narration for
that scene. Do not film a product that is not installed.

## Status on 2026-10-08

This plan was written before any of the software in this repository
existed. It is kept as written below. What has changed since:

- **Built and running in the lab:** the cloud admin and platform
  engineer Terraform, Argo CD, a DSM database, and Private AI Services
  with the Qwen model on CPU. The quickstart in the top-level README
  builds all of it. This covers "Terraform plus Argo CD against VCF
  Automation" and DSM from the list of what was not there.
- **In git, handed to Argo CD:** the users VM Service VM and the DSM
  catalog database, in `gitops/music-store/`. This is both moves of
  step 4.
- **Not started:** the store, cart, and orders containers on VKS
  through Argo CD (step 2), the Oracle on Tanzu (step 3), and the
  security episode (step 6).
- **Still true:** no GPU. Istio, OPA, Headlamp, SSP, vDefend DFW, and
  Antrea policy are not in the repository.
- **Changed:** the master is on GitHub. The lab git server holds the
  Terraform state: see `docs/terraform-state.md`.

Where this plan and `docs/decisions.md` disagree, the decisions are
newer.

## What can be shown now

- A VCF lab with a Supervisor and a VKS cluster.
- Tanzu Application Service, with a private language model. CPU is
  acceptable. Do not wait for a GPU, and do not say GPU on camera
  until a GPU is allocated.
- AgentMinder, with a VCF door and a separate Kubernetes door.
- Avi.
- The music-store application as containers: store, cart, orders,
  users, a PostgreSQL container, and a traffic generator. Users is
  not a VM. PostgreSQL is not DSM.
- This git repository as the master. The lab git server replicates
  it. It does not become a second master.

## What the design asks for that is not there

DSM, the VM Service users VM, TuneD, Terraform plus Argo CD against
VCF Automation, vDefend DFW, Antrea policy, SSP, Istio, OPA,
Headlamp, and a GPU tenancy. The Metal Oracle source is in
`NiranEC77/music-store-ai`: it calls `album_count`, `list_albums`,
and `list_orders`, and the same tools are on `POST /mcp`. Cart,
orders, and users source is in that repository too. The traffic
generator source is still not.

Videos 2, 3, and 4 are not written. Video 5 is an edit of films
that do not exist.

## Order of work

### 1. Put the application in this repository

The container manifests are in `app/music-store/`. They are the
starting point: a container database, not DSM, and a container
users service, not a VM. The Oracle, cart, orders, and users
source stays in `NiranEC77/music-store-ai`. This plan does not
pretend the migration already happened.

### 2. Deploy that starting application on VKS

Store, cart, orders, and the traffic generator. Prove a browse, a
cart write, and an order. This is the only application scene that
can be filmed before the gaps in section 3 are built.

### 3. Build the Metal Oracle as its own Tanzu app

The chat service source is in `NiranEC77/music-store-ai`. It is a
new app. Not the company infrastructure agent.

- Private model. CPU is enough.
- MCP tools that read inventory and orders from the store. The
  agent speaks the tool result. It does not invent a count.
- AgentMinder in front of the tools that the demo must allow or
  refuse. Avi serves the route. AgentMinder does not replace Avi.

Port 5005 in the gap analysis is the chat service. Do not bind it
until the store it reads is the one deployed in step 2.

### 4. One infrastructure move

Do one of these, then film it. Do not narrate both in one scene.

- Database to DSM, if DSM is installed and can be called from the
  automation the demo will use.
- Users service to a VM Service VM, if that service is available
  on the Supervisor.

The one that is not installed stays a later episode. The script's
Day 0 scene currently requires both, plus Argo CD, in a single
pass. Cut that scene down to the migration that is real.

### 5. GitOps after the manifests are the ones you mean

Argo CD and Terraform are how the filmed deploy should look. They
are not required to prove the store or the Oracle. Wire them when
this repository holds the manifests Argo CD would apply, including
only the infrastructure objects that exist.

### 6. Security episode last

Video 4 needs a policy that is actually loaded and a flow that is
actually blocked.

- A DFW or Antrea rule that allows the store and refuses something
  else.
- A shown deny. Not a sentence that says Terraform applied the rule.
- AgentMinder revoking the Oracle is a separate beat from vDefend.
  Do not combine them until both products are in the lab.

Istio, OPA, Headlamp, and SSP stay off the script until they are
installed. Video 2 cannot trace latency through Istio if Istio is
not there. Use the tools that are present, or install one tool and
then write that scene.

### 7. Then finish the script

Rewrite Video 1 so each shot matches a step above. Write Videos 2,
3, and 4 only after the failure, the scale event, and the blocked
flow have been done once off camera. Video 5 is the edit.

## Suggested episode map

| Episode | Film when | Do not say |
|---|---|---|
| The store on VKS | Step 2 is up | DSM, VM Service, GPU |
| The Oracle | Step 3 answers from a tool | A guessed album count |
| One data move | Step 4, one product | Both migrations at once |
| Declarative deploy | Step 5, Argo CD synced | A namespace that was clicked by hand |
| The locked-down path | Step 6, a real deny | "Terraform applied it" without the deny |
| Load and scale | Avi or the Supervisor quota is actually changed | Istio, if it is not installed |
