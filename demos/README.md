# Demos

Each folder here is one demo you can run on the built lab, with
everything it needs: a README that takes you from nothing to the end of
the demo, and the scripts and manifests it runs.

| Demo | What it shows |
|---|---|
| [pen-test-dashboard](pen-test-dashboard) | The music store's security layers on the Grafana board "Pen test": take the Antrea default deny and the Avi WAF out, the attacks get through, put them back |
| [pen-test-manual](pen-test-manual) | The same layers by hand: an attacker pod next to the store, its five attacks blocked by the default deny and the Avi WAF, with the results in the terminal |
| [platform-engineer-ui](platform-engineer-ui) | A five-minute UI walk as the platform engineer, starting in VCF Automation: the namespaces, cluster, database, VM and private AI model behind the music store, and the Terraform and Argo CD that set them up |
| [storage-troubleshooting](storage-troubleshooting) | A slow checkout followed down in VCF Operations, from the shop's pods through the VKS worker VM, its host and vSAN, to an IOPS-limited storage policy on the cart and order disks |
| [platform-engineer-automation](platform-engineer-automation) | The platform engineer's automation end to end: a Terraform change through the `platform-engineer` workflow, then a git change through Argo CD, until VKS adds a worker to the music store cluster |
| [cloud-admin-automation](cloud-admin-automation) | The cloud admin's automation end to end: a change to the org's quota through the `cloud-admin` workflow and its Terraform roots, to VCF Automation |
| [agentic-ops-automation](agentic-ops-automation) | The agentic ops engineer's automation end to end: grant an agent a tool in AgentMinder with the `agentic-ops` workflow, change its skill, `cf push` through `tanzu-apps`, and watch it call the VKS cluster in an incident |
| [golden-path](golden-path) | One line of the shop's code, from a commit to production: GitHub Actions, a Tekton build on a trusted Tanzu Hub base image, Harbor, a deploy pull request, and Argo CD |
| [vdefend-virtual-patching](vdefend-virtual-patching) | An exploit against the users VM (Apache CVE-2021-41773) logged in detect mode and reset in prevent mode by vDefend Distributed IDPS, while the VM's health check still answers |

## What a demo folder holds

- `README.md`, in this order:
  1. What the demo shows and which layers it touches. No persona
     roles: anyone with the access in step 2 runs it.
  2. **Before the demo**: the tools, the access, and the vcf contexts
     the presenter needs, made with their own login. Say which
     Supervisor Namespace each context must point at, and how to find
     its generated suffix.
  3. **Run the demo**: numbered steps, each with the command, what it
     prints, and what the audience sees.
  4. **After the demo**: how to put the lab back, and how to check it.
  5. **Troubleshooting**: the errors a presenter is likely to meet.
- The scripts the presenter runs, and any manifests only the demo uses.

Scripts take the context they need as an argument. They never default
to one person's context, and they print no secret.

What several demos share is in `lib/`: `lib/github.sh` opens and merges
a pull request through the GitHub API, starts a workflow and waits for
it. The demos that change `main` use it, so their `reset.sh` puts the lab
back the same way the demo changed it.

What runs all the time is not here: it is synced by Argo CD from
`gitops/`, like the pen test's probes in
`gitops/music-store-platform/pen-test.yaml`. A demo folder holds only
what a person starts.
