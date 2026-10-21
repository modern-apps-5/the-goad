# Guest overlay

`gitops/music-store` is still the users VM Service VM, the DSM
catalog, and the VKS cluster. This directory does not copy that tree.

The storefront here is the shop that was already running elsewhere:
store, cart, orders, and chat. The source is `src/` and the cover
files are `covers/`. Images are public `python:3.12-slim`. There is
no pull secret.

`backing.yaml` publishes `users-service` and `postgres-service`.
The store and chat use those names. The database password is
`store-db`, filled at apply from the password already published in
`app/music-store`. This directory does not copy it.

Chat reads `metal-oracle-model` (`base-url`, `api-key`, `model`).
Apply fills that secret from `QWEN_BASE_URL`, `QWEN_API_KEY`, and
the model id `qwen`. `OPENAI_TLS_VERIFY` is `false`.

`ingress.yaml` keeps the shop hostname on class `avi-lb`. The
storefront readiness probe allows a long `GET /` because the albums
view delay is still in place.

The container Postgres from the other org is not applied. Orders
stay on sqlite at `ORDER_DB_PATH=/tmp/orders.db`.
