# Zammad

Two copies. Only one of them was serving the demo.

`cluster/zammad.yaml` is the guest-cluster attempt. The nodes evicted it for low disk. Do not apply it. The database password in that file is the published Zammad compose default.

`host/` is what actually answered on port 8080. `run.py` starts the official images with bubblewrap because the Docker socket was not usable. `extract.py` unpacks an OCI layout into a rootfs. `start-postgres.sh` is the database process alone.

Elasticsearch is off. Zammad uses its database search. Postgres is on port 5433. The app is on 3010. Nginx is on 8080.

The image rootfs, the database files, and the admin token are not in this repo. Set `ZAMMAD_ROOT` to the directory that holds `rootfs/` and `data/`. Put `ZAMMAD_URL`, `ZAMMAD_TOKEN`, `ZAMMAD_USER`, and `ZAMMAD_PASSWORD` in the repo-root `.env` from `orchestrator/.env.example`.
