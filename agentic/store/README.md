# Guest overlay

The Red Lab store is [gitops/music-store](../../gitops/music-store):
the users VM Service VM, the DSM catalog, and the VKS cluster.
This directory does not copy that tree.

`backing.yaml` publishes the Service names `users-service` and
`postgres-service` inside the guest cluster. `ingress.yaml` keeps
the shop hostname. The container files in `app/music-store` are the
earlier shape and are not applied.
