# AgentMinder step

The incident response agent and the three domain diagnostic agents do not hold a gateway password. Each Cloud Foundry app has an AgentMinder sidecar. The sidecar authenticates with that agent's own client identity and sends the minted bearer token to AgentMinder.

A granted call is a tool on that agent's role. The load balancer diagnostic agent has no Kubernetes role, so a Kubernetes call from that identity is denied. Both results belong in the AgentMinder audit.

Avi tools run on the local Avi MCP. Avi is not an AgentMinder resource server in this lab, so those calls are not the allow/deny proof.
