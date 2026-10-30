# Music store source

The developer's code for the shop. One directory for each service:

| Directory | Service | Port |
|---|---|---|
| `store/` | The storefront. Ships `static/covers` | 5000 |
| `cart/` | The cart | 5002 |
| `order/` | Orders | 5001 |
| `chat/` | The chat | 5005 |

Each directory needs `app.py` and `requirements.txt`, and anything else
the service ships, such as `static/` for the store.

You do not build or deploy. When you push to `main`, the workflow
[music-store-images.yml](../../.github/workflows/music-store-images.yml)
starts the platform engineer's pipeline in
[gitops/platform-tools-builds](../../gitops/platform-tools-builds). It
builds an image for each service and opens a deploy pull request that
sets the new image tags.

The Dockerfile is the platform engineer's, not part of these directories:
[Dockerfile](../../gitops/platform-tools-builds/dockerfiles/python/Dockerfile).
It runs `python app.py`.
