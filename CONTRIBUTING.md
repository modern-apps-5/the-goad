# Contributing

## Repository layout

```
terraform/cloud-admin/org/     Stage 1, provider (System) org scope: creates the org
terraform/cloud-admin/org-config/  Stage 2, inside the org: users, roles, Service Engine Group, AgentMinder's cluster
terraform/cloud-admin/agentminder/ Stage 3, AgentMinder on that cluster, with Helm
terraform/cloud-admin/ops/      VCF Operations content: platform observability dashboards (dashboards/*.json) and alerts
terraform/platform-engineer/   Inside the org: namespaces, Secret Store, Argo CD handoff, Tanzu Platform space
  manifests/                   Manifests that Terraform applies
terraform/agentic-ops/         The incident demo's agents registered in AgentMinder, and the am-* and sc-* services
terraform/security-admin/      The vDefend guardrails for the music store, in NSX
terraform/runner/              The self-hosted runner for the workflows. Not a persona; applied by hand
gitops/<namespace key>/        What Argo CD syncs into that namespace: private-ai, music-store, platform-tools
gitops/music-store-platform/   The platform engineer's part inside the music-store VKS cluster
apps/music-store/              The developer's code: store, cart, order, chat. The platform engineer builds it into images
gitops/music-store-apps/       The shop's containers, deployed into the VKS cluster by the platform engineer, from the built images
gitops/platform-tools-builds/  The image build: Tekton pipeline, tasks, and the Dockerfile template, in the platform tools cluster
gitops/platform-tools-apps/    What runs in the platform tools cluster: the incident demo's Zammad, Grafana, Prometheus
tanzu/<space>/                 Cloud Foundry apps that tanzu-apps.yml pushes into that space of org Goad
scripts/                       What a person runs by hand: setup once, the SDK mirror, and the incident walk
demos/<demo>/                  One demo each: its run guide end to end, and the scripts the presenter runs
.github/workflows/             One Terraform workflow for each persona, tanzu-apps.yml, and music-store-images.yml
.github/actions/cf-login/      Installs the cf CLI and logs in to Tanzu Platform as goad-deployer
.github/actions/cf-token/      Gets a Tanzu Platform token for goad-deployer, for Terraform
docs/                          Design, script, plan, decisions
```

## Where a file goes

One rule decides where a file goes: if Terraform applies it, it is under
`terraform/`. If Argo CD syncs it, it is under `gitops/`. If `cf push`
pushes it, it is under `tanzu/`. If a presenter runs it during a demo,
it is under `demos/<demo>/`. If a person runs it otherwise, it is under
`scripts/`.

## Adding a namespace for Argo CD

To give Argo CD another namespace, add it to `namespaces` in
`terraform/platform-engineer` and add the directory `gitops/<key>/`.
`music-store` and `platform-tools` were added that way. Manifests under
`gitops/<namespace key>/` do not set a namespace. A directory that syncs
into a VKS cluster has its own `ManagedEntity` and Application in
`terraform/platform-engineer/gitops.tf`.

## Workflows

The workflows run on a self-hosted runner inside the lab, with the lab's
secrets in scope, and this repository is public. So:

- No workflow runs on `pull_request` or `pull_request_target`. A run starts
  only by hand (`workflow_dispatch`) or on a push to `main`. Do not add a
  pull request trigger to a workflow that runs on the self-hosted runner.
- Every action from outside this repository is pinned to a commit SHA,
  with its version in a comment. Dependabot opens a pull request when an
  action has a new release.
- A workflow from a pull request by anyone outside the organization waits
  for a maintainer's approval before it runs.
