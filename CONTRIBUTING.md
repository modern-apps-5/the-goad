# Contributing

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
