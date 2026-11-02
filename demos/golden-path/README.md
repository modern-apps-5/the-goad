# Golden path: from a commit to production

A ten-minute browser demo of the golden path the platform engineer owns
for the music store. Change one line of the shop's code in GitHub and
follow it to production: GitHub Actions, a Tekton build on a trusted
Tanzu base image, Harbor, a deploy pull request, and Argo CD.

The point: the developers write code and nothing else. The platform
engineer owns the way it is built and delivered, the same for every app,
from trusted sources.

This demo changes `main`: it merges two pull requests, and a third to
put the change back after the demo.

## Steps

| Time | Step | Screen |
|---|---|---|
| 0:00 | 1. The developer's view | GitHub, `apps/music-store/` |
| 0:40 | 2. The trusted base image | Tanzu Hub, then the Dockerfile template |
| 1:40 | 3. Change the code | GitHub, edit and merge |
| 2:30 | 4. The build | GitHub Actions, `music-store-images` |
| 3:30 | 5. Tekton | Argo CD, `platform-tools-builds` |
| 4:30 | 6. The deploy pull request | GitHub |
| 5:30 | 7. Argo CD rolls it out | Argo CD, `music-store-apps` |
| 6:30 | 8. The change in production | The shop |

The build takes about three minutes. Step 5 fills that time.

## Before the demo

### What you need

- A browser on the lab network that resolves `*.goad.gpu.set.lab`.
- Write access to the GitHub repository `modern-apps-5/the-goad`, to
  merge to `main`.
- A VCF Automation user in org `goad`, in the group
  `ans-platform-engineer@set.lab`, to log in to Argo CD.
- A login to Tanzu Hub, `https://hub.sys.goad.gpu.set.lab`.

### Check the lab

1. In VCF Automation, open namespace `platform-<suffix>` (not
   `platform-tools-<suffix>`), the GitOps tab, and click the button on
   the Argo CD instance. Log in with "VCF Automation".
2. Check `music-store-apps` and `platform-tools-builds` are Synced and
   Healthy.
3. In GitHub Actions, check the last run of `music-store-images` is
   green, and no deploy pull request from it is open.

### Browser tabs

1. GitHub: `apps/music-store/`.
2. Tanzu Hub, the content catalog.
3. GitHub: `gitops/platform-tools-builds/dockerfiles/python/Dockerfile`.
4. GitHub: Actions, `music-store-images`.
5. Argo CD, Applications.
6. The shop, `https://music.goad.gpu.set.lab`.

## Run the demo

### 1. The developer's view (0:00)

Tab 1, `apps/music-store/`.

**Show**

- One folder per service: `store`, `cart`, `order`, `chat`.
- Each has `app.py` and `requirements.txt`, and nothing else: no
  Dockerfile, no Kubernetes YAML, no pipeline.

**Why**: the developers own the code. Everything else is the platform
engineer's, so every app is built and deployed the same way.

### 2. The trusted base image (0:40)

Tab 2, Tanzu Hub, then tab 3, the Dockerfile.

**Show**

- In Tanzu Hub, the Bitnami Python image on Photon 5.
- In the Dockerfile, the `FROM` line:
  `depot.kube-system.svc/tanzu-platform-content/containers/photon-5/python:...`.
- The `USER 1000:1000` line.

**Why**: every image starts from a base Broadcom builds and maintains,
not one from Docker Hub. It is pulled through the lab's own Harbor, a
proxy cache the cloud admin owns, so builds need no Broadcom login. One
template, owned by the platform engineer, for every Python service.

### 3. Change the code (1:40)

Tab 1, `apps/music-store/store/app.py`. Edit in the browser.

**Show**

- Find `<h1>🤘 Metal Music Store</h1>` and change the text, for
  example to `🤘 Metal Music Store, live from VCF`.
- Commit to a new branch, open the pull request, merge it.

**Why**: this is all a developer does. A reviewed commit to `main` is
the start of the path.

### 4. The build (2:30)

Tab 4, Actions, the new `music-store-images` run.

**Show**

- It started by itself, on the push to `main`.
- The step "Start the PipelineRun": the run's name and the tag, the
  first 12 characters of the commit.
- The step "Wait for the build", running.

**Why**: GitHub Actions only starts the build. The runner has a login
that can start and read PipelineRuns in one namespace, and nothing else.

### 5. Tekton (3:30)

Tab 5, Argo CD, Application `platform-tools-builds`, tree view.

**Show**

- The `Pipeline` `music-store-images`: clone the commit, then one
  BuildKit build per service.
- The `TektonConfig`, and the Harbor CA and push login the build uses.

**Why**: the build runs on the platform tools VKS cluster, with Tekton
from the VKS addon. The pipeline is in git like everything else. Images
go to Harbor in VCF, not a public registry.

### 6. The deploy pull request (4:30)

Tab 4, the finished run, then the pull request it opened.

**Show**

- The run's summary: four images,
  `depot.kube-system.svc/music-store/<service>:<tag>`.
- The pull request "Deploy the music store images `<tag>`": its diff
  changes `newTag` in `gitops/music-store-apps/kustomization.yaml`.
- Merge it.

**Why**: building is not deploying. Every deploy is a pull request, so
it is reviewed, recorded and easy to roll back.

### 7. Argo CD rolls it out (5:30)

Tab 5, Argo CD, Application `music-store-apps`, tree view. Click Refresh
if it has not synced yet.

**Show**

- The new ReplicaSets and pods coming up, the old ones going.
- A pod's image: the new tag.

**Why**: Argo CD deploys what git says. No one ran `kubectl`.

### 8. The change in production (6:30)

Tab 6, the shop. Reload.

**Show**: the new heading.

**Why**: from a one-line commit to production, through a path the
developer never had to build.

## After the demo

Put the heading back the same way: edit `app.py` back, merge, wait for
the build, merge the deploy pull request. Check `music-store-apps` is
Synced and Healthy and the shop shows the old heading.

## Troubleshooting

- **No `music-store-images` run starts**: the change must be on `main`
  and under `apps/music-store/`, and not only in a Markdown file.
- **The run fails in "Wait for the build"**: the run prints the
  PipelineRun's message and the logs of each build. A pull from
  `tanzu-platform-content` that fails usually means the cloud admin's
  Broadcom registry token expired.
- **The run ends with "No tag to change"**: `music-store-apps` already
  uses this commit's tag, so there is nothing to deploy.
- **Argo CD does not sync after the merge**: click Refresh on
  `music-store-apps`. If it is OutOfSync and stays so, click Sync.
- **The shop shows the old heading**: the browser cached it. Reload
  without the cache.
