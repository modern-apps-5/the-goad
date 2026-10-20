# Music store containers

These manifests are the store, cart, orders, and traffic generator. They
use Service names, not addresses, and they do not name an organization.
`kustomization.yml` lists exactly these four. The Application
`music-store-dev-app` deploys them onto the VKS cluster, from
[gitops/music-store-dev/app](../../gitops/music-store-dev/app).

The users service and the catalog are not these Deployments. The users
service is a VM Service VM in
[gitops/music-store-dev/users-vm](../../gitops/music-store-dev/users-vm),
whose Service is `users-service`. The catalog is a DSM `PostgresCluster`
in [gitops/music-store](../../gitops/music-store), whose Service is
`postgres-service`. The container users file and the container database
file in this directory are the earlier shape. `kustomization.yml` does
not list them.

Chat is not deployed on the VKS cluster. The walkthrough script deploys
it to Tanzu with `cf push`. `kustomization.yml` does not list it. Chat
reads secret `metal-oracle-model`. The base URL is the Private AI
ingress of the org the demo creates, path
`/api/v1/compatibility/openai/v1`, model `qwen`. The token is not in git.

The Oracle, cart, orders, and users source lives in https://github.com/NiranEC77/music-store-ai. These files still pull the published images.
