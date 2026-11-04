# GitHub workflows

The persona roots can also run in GitHub Actions, on a runner in the
lab. There is one Terraform workflow for each persona, one workflow
that pushes the incident apps, and one that builds the music store's
images:

| Workflow | What it runs |
|---|---|
| `cloud-admin` | Three jobs, in order: `org` runs `terraform/cloud-admin/org`, then `org-config` runs `terraform/cloud-admin/org-config`, then `agentminder` runs `terraform/cloud-admin/agentminder`. A fourth job, `ops`, runs `terraform/cloud-admin/ops` on its own, in parallel with `org`. Its only secret is `OPS_ADMIN_PASSWORD` |
| `platform-engineer` | `terraform/platform-engineer` |
| `agentic-ops` | `terraform/agentic-ops`. Needs the repository secrets `AGENTIC_OPS_AGENTMINDER_CLIENT_ID` and `AGENTIC_OPS_AGENTMINDER_CLIENT_SECRET`: see [its README](../terraform/agentic-ops/README.md) |
| `security-admin` | `terraform/security-admin`. Its only secret besides the state token is `SECURITY_ADMIN_NSX_PASSWORD`. See [its README](../terraform/security-admin/README.md) |
| `tanzu-apps` | `cf push` of each app in `tanzu/metal-music-app-agentic-system`, then their network policies. See [its README](../tanzu/metal-music-app-agentic-system/README.md) |
| `music-store-images` | A Tekton PipelineRun on the platform tools cluster that builds the music store's images, then a pull request with the new image tags. Its only secret is `MUSIC_STORE_BUILD_KUBECONFIG` |

A Terraform workflow runs only when a person starts it. Nothing runs on a
pull request or on a push. In GitHub: Actions, the workflow, **Run
workflow**. Or:

```sh
gh workflow run cloud-admin.yml                 # plan
gh workflow run cloud-admin.yml -f apply=true   # plan, then apply
```

A run plans, and the plan is on the run's summary page. It applies only
with `apply`, and only on `main`.

Every job that runs on the lab's runner uses the GitHub environment
`lab`, which holds the lab's secrets and only deploys from `main`. A run
of these workflows on another branch stops before it starts, and never
sees a secret. To try a workflow change, merge it, then run a plan.

`tanzu-apps` runs on every push to `main` that changes
`tanzu/metal-music-app-agentic-system`, the workflow itself, or the
`cf-login` action, and by hand. It does not plan or apply; it pushes.

`music-store-images` runs on every push to `main` that changes
`apps/music-store/` or the Dockerfile templates in
`gitops/platform-tools-builds/dockerfiles/`, other than Markdown, and by
hand.

Nothing orders the workflows. On a first build: `cloud-admin`, then
`platform-engineer`, then `agentic-ops`, then `security-admin`, then
`tanzu-apps`. The cloud admin copies the two `AGENTIC_OPS_AGENTMINDER_*`
secrets after `cloud-admin` has installed AgentMinder and before
`agentic-ops` runs.

The workflows use the same state and the same shared secrets as a
machine does, so a run and a teammate's `terraform apply` are the same
thing. The secrets are repository secrets in GitHub.
[terraform/runner/README.md](../terraform/runner/README.md) lists them and
says how the runner is built.
[Decision 25](decisions.md) has the reasons.
