# Music store containers (earlier shape)

Nothing in this directory is deployed. The shop that runs is
[gitops/music-store-dev/app](../../gitops/music-store-dev/app), which
holds its own manifests and source, because Argo CD's kustomize does not
load files from outside the directory it syncs. The users service is the
VM in [gitops/music-store-dev/users-vm](../../gitops/music-store-dev/users-vm),
and the catalog is the DSM `PostgresCluster` in
[gitops/music-store](../../gitops/music-store).

These manifests are the earlier shape: published images, a container
users service, and a container database. They are kept as a record.
`gateway-api/` is the optional L7 HTTPRoute and Gateway objects for the music-store-1-service

The Oracle, cart, orders, and users source lives in https://github.com/NiranEC77/music-store-ai. These files still pull the published images.
