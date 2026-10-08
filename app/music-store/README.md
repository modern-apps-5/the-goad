# Music store containers

These manifests are the store, cart, orders, and chat. They use Service
names, not addresses, and they do not name an organization.

The users service and the catalog are not these Deployments. They are
[gitops/music-store](../../gitops/music-store): a VM Service VM whose
Service is `users-service`, and a DSM `PostgresCluster` whose Service is
`postgres-service`. The container users file and the container database
file in this directory are the earlier shape. `kustomization.yml` still
lists them.

Chat reads secret `metal-oracle-model`. The base URL is the Private AI
ingress of the org the demo creates, path
`/api/v1/compatibility/openai/v1`, model `qwen`. The token is not in git.

The Oracle, cart, orders, and users source lives in https://github.com/NiranEC77/music-store-ai. These files still pull the published images.
