# Agentic ops automation: give an agent a new tool, down to VKS

A twenty-minute demo of the agentic ops engineer's automation, end to
end. The Kubernetes diagnostic agent learns to check the music store
cluster's nodes. First grant it the tool in AgentMinder with Terraform,
then change the agent's skill in git. Follow both: the `agentic-ops`
workflow, AgentMinder, the `tanzu-apps` workflow and `cf push` to Tanzu
Platform, and an incident the agent investigates, through AgentMinder,
down to the VKS cluster.

The point: the agentic ops engineer ships agents the way developers ship
apps, from git. What an agent may call is a reviewed change too, and
AgentMinder enforces it. The agents hold no tool logins.

This demo changes `main`: it merges two pull requests. `reset.sh` merges a
third to put the lab back.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The agents | Tanzu Hub, space `metal-music-app-agentic-system` |
| 0:40 | 2. What the k8s agent may call | AgentMinder console |
| 1:20 | 3. The tool nobody granted | GitHub, `k8s_mcp.py` |
| 2:00 | 4. Grant it | GitHub, `agentminder.tf`, edit and merge |
| 2:40 | 5. Run the Terraform | GitHub Actions, `agentic-ops` |
| 4:00 | 6. AgentMinder has it | AgentMinder console |
| 4:30 | 7. Teach the agent | GitHub, the agent's `SKILL.md`, edit and merge |
| 5:10 | 8. The push | GitHub Actions, `tanzu-apps` |
| 7:00 | 9. An incident | Terminal |
| 15:00 | 10. Ask the agents | The incident chat |
| 17:00 | 11. Down to VKS | VCF Automation, then AgentMinder |

The push takes about ten minutes. Steps 8 and 9 fill that time.

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- Write access to the GitHub repository `modern-apps-5/the-goad`, to
  merge to `main` and to run workflows.
- A login to the AgentMinder console,
  `https://agentminder.goad.gpu.set.lab/default/ui/v1/adminconsole/`.
- A login to Tanzu Hub, `https://hub.goad.gpu.set.lab`, that can see org
  `Goad`.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`, for the music store's namespace.
- A Zammad API token, for `incident.sh start`.
- For the scripts: `gh`, logged in with that GitHub access, the `vcf`
  CLI, `kubectl`, `jq`, `perl` and `python3`.

### Make your vcf context

`incident.sh` slows the music store's catalog, inside its VKS cluster. It
reads the cluster's kubeconfig from the cluster's Supervisor Namespace,
`music-store-<suffix>`. You need a vcf context for it, logged in as
yourself.

1. Make a context for the org. The name is yours; `goad` is used below.
   Use an API token that you made in VCF Automation:

   ```bash
   vcf context create goad --endpoint https://auto.gpu.set.lab --type cci \
     --tenant-name goad --api-token <your API token>
   ```

2. Find the one for the music store:

   ```bash
   vcf context list | grep ':music-store-'
   STORE_CONTEXT=goad:music-store-8q8l6:default-project
   ```

   If the session expires, `vcf context refresh goad`.

### Check the lab

```bash
demos/agentic-ops-automation/check.sh
```

It checks `main` does not grant or call `k8s_list_nodes` yet, the last
`tanzu-apps` run on `main` succeeded, and the `agentic-ops` workflow, run
as a plan only, plans no change. It ends with `Ready for the demo.`

A plan with changes means someone changed AgentMinder or `main` by hand.
Find out whose before the demo; the demo's apply would apply them too.

Run one incident walk the day before (steps 9 and 10, then
`incident.sh "$STORE_CONTEXT" stop`), to see the chat answer before the
audience does.

### Browser tabs

1. Tanzu Hub, org `Goad`, space `metal-music-app-agentic-system`.
2. AgentMinder console, the MCP server `goad-k8s-mcp`.
3. GitHub:
   `tanzu/metal-music-app-agentic-system/metal-k8s-mcp/k8s_mcp.py`.
4. GitHub: `terraform/agentic-ops/agentminder.tf`.
5. GitHub: Actions, `agentic-ops`.
6. GitHub:
   `tanzu/metal-music-app-agentic-system/k8s-diagnostic-agent/.agents/skills/k8s_diagnostic_agent/SKILL.md`.
7. GitHub: Actions, `tanzu-apps`.
8. The incident chat,
   `https://incident-response-agent.apps.goad.gpu.set.lab/`.
9. VCF Automation, `https://auto.gpu.set.lab`, org `goad`, namespace
   `music-store-<suffix>`, the cluster `music-store`.

## Run the demo

### 1. The agents (0:00)

Tab 1, the space's apps.

**Show**

- The chat `incident-response-agent`, the orchestrator
  `metal-incident-live`, the three diagnostic agents, the three MCP
  servers, `pii-scrub`. All running.
- `k8s-diagnostic-agent`, its bound services: `goad-qwen`, the model,
  `am-k8s-diagnostic-agent` and `sc-k8s-diagnostic-agent-k8s`.

**Why**: the agents are Cloud Foundry apps on Tanzu Platform, in a space
the platform engineer made. The agent's only credential is its own
AgentMinder client, in a service Terraform made. It has no login to
Kubernetes.

### 2. What the k8s agent may call (0:40)

Tab 2, `goad-k8s-mcp`, then the policy `py-goad-k8s`.

**Show**

- The MCP server's five tools: `k8s_list_deployments`, `k8s_list_pods`,
  `k8s_events`, `k8s_pod_logs`, `k8s_list_namespaces`.
- The policy grants them to the client `py-goad-k8s`, the k8s agent.

**Why**: every tool call goes through AgentMinder. It checks who the agent
is and whether the tool is granted. The cloud admin runs AgentMinder for
the org; the agentic ops engineer registers their agents in it.

### 3. The tool nobody granted (1:20)

Tab 3, `k8s_mcp.py`. Search for `k8s_list_nodes`.

**Show**: the MCP server has a tool `k8s_list_nodes`, "List cluster nodes
and how many are Ready".

**Why**: the server has it, but AgentMinder does not know it. No agent can
call it. A tool on a server is not a tool an agent may use.

### 4. Grant it (2:00)

Tab 4, `agentminder.tf`. Edit in the browser.

**Show**

- In `mcp_servers`, `k8s`, add a line after `"k8s_list_namespaces",`:

  ```hcl
        "k8s_list_nodes",
  ```

- Commit to a new branch, open the pull request, merge it.

**Why**: the agents' identities and what each may call are Terraform, in
the agentic ops engineer's own root. Granting a tool is a reviewed pull
request.

### 5. Run the Terraform (2:40)

Tab 5, Actions, `agentic-ops`. Run workflow, tick "Apply after the plan",
run it on `main`.

**Show**

- The job runs on a `self-hosted, lab` runner.
- The run's summary: updates to `restapi_object` resources keyed `k8s`,
  the MCP server and the k8s client's policy. Only each resource and its
  action, no values.
- The step Apply, green.

**Why**: AgentMinder returns client secrets when Terraform reads it, so
this workflow never prints Terraform's output. The login to AgentMinder is
a GitHub secret. A person starts the run, and it applies only on `main`
and only when ticked.

### 6. AgentMinder has it (4:00)

Tab 2, reload `goad-k8s-mcp`, then `py-goad-k8s`.

**Show**: six tools, `k8s_list_nodes` among them, and the policy grants it.

**Why**: the grant is in place before any agent uses it.

### 7. Teach the agent (4:30)

Tab 6, `SKILL.md`. Edit in the browser.

**Show**

- Under `## Steps`, after step 4, add:

  ```markdown
  5. **Nodes.** Call `k8s_list_nodes`. A node whose `ready` is false is a critical finding. A node with `disk_pressure` true is a warning finding. If every node is ready, write one `info` finding that quotes `count`.
  ```

- Commit to a new branch, open the pull request, merge it.

**Why**: the agent's behavior is its skill, a Markdown file in git. The
agentic ops engineer changes it like code.

### 8. The push (5:10)

Tab 7, Actions, the new `tanzu-apps` run.

**Show**

- It started by itself, on the push to `main`.
- One job per app, and `network-policies` last.
- The job `push k8s-diagnostic-agent`: the AgentMinder SDK pulled from a
  private package, then `cf push`.

**Why**: nobody pushes an agent by hand. Every change to the agents in
git deploys them again, as `goad-deployer`, with the apps' secrets from
GitHub secrets.

### 9. An incident (7:00)

In a terminal, while the push runs:

```bash
ZAMMAD_TOKEN=<your token> demos/agentic-ops-automation/incident.sh "$STORE_CONTEXT" start
```

```
Database latency applied: catalog queries sleep 10 seconds.
store HTTP 200 in 10235 ms
opened ticket 34012: Metal Music Store slow: checkout and catalog pages taking 10+ seconds
```

**Show**: the shop's catalog is slow, and the ticket is open.

**Why**: a real incident for the agents to work on, in the store's real
cluster.

### 10. Ask the agents (15:00)

Wait for the `tanzu-apps` run to be green. Tab 8, the chat. Type:

`pick up the latest incident ticket and enrich it`

**Show**

- The orchestrator calls the three diagnostic agents.
- The k8s agent's findings: the slow query, and a nodes finding from
  `k8s_list_nodes`, with the node count and every node Ready.

**Why**: the agent used the new tool, because git said to and AgentMinder
allowed it.

### 11. Down to VKS (17:00)

Tab 9, the cluster `music-store`, then tab 2.

**Show**

- The cluster's control plane and workers: the same nodes, and the same
  count, as the agent's finding.
- In AgentMinder, the k8s agent's call to `k8s_list_nodes`.

**Why**: the call went from the agent on Tanzu Platform, through
AgentMinder, to the MCP server, to the VKS cluster's API. Each hop is
VCF, and each change to it came from git.

## After the demo

```bash
demos/agentic-ops-automation/incident.sh "$STORE_CONTEXT" stop
demos/agentic-ops-automation/reset.sh
```

`incident.sh stop` makes the catalog fast again. It does not close the
ticket. `reset.sh` opens and merges one pull request that takes the step
and the grant out, waits for the `tanzu-apps` run it starts, then runs
the `agentic-ops` workflow with apply. It takes about fifteen minutes.
Then check:

```bash
demos/agentic-ops-automation/check.sh
```

## Troubleshooting

- **The k8s agent lists `k8s_list_nodes` in `tools_denied`**: AgentMinder
  does not grant it. Check the `agentic-ops` run applied, and step 6.
- **The plan in step 5 changes more than the `k8s` resources**: someone
  changed AgentMinder or `main` since `check.sh`, and the run applied
  their change too. Find out whose it is.
- **No `tanzu-apps` run starts**: the change must be on `main` and under
  `tanzu/metal-music-app-agentic-system/`.
- **A push job fails with `InsufficientResources`**: the foundation's one
  Diego cell is full. See the lessons in
  `tanzu/metal-music-app-agentic-system/README.md`.
- **`incident.sh start` says the pages are not slow yet**: the delay did
  not apply. Run `incident.sh stop`, then `start` again.
- **The chat answers `URLError` at once**: a network policy or an
  `apps.internal` route is missing. Run the `tanzu-apps` workflow again
  from Actions.
- **`You must be logged in to the server`**: the vcf session expired.
  `vcf context refresh goad`, then run the script again.
