#!/bin/bash
ROOT="${ZAMMAD_ROOT:-/home/cursor/var/zammad}"
: > "$ROOT/logs/postgres.log"
exec bwrap --unshare-user --uid "$(id -u)" --gid "$(id -g)" --unshare-pid \
  --bind "$ROOT/rootfs/postgres" / \
  --proc /proc --dev /dev --tmpfs /tmp --tmpfs /run --tmpfs /dev/shm \
  --ro-bind /etc/resolv.conf /etc/resolv.conf \
  --ro-bind /etc/hosts /etc/hosts \
  --bind "$ROOT/data/pg" /var/lib/postgresql/data \
  --bind "$ROOT/data/pg-init" /docker-entrypoint-initdb.d \
  --setenv PATH /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --setenv PGDATA /var/lib/postgresql/data \
  --setenv POSTGRES_USER postgres \
  --setenv POSTGRES_PASSWORD zammad \
  --setenv POSTGRES_DB postgres \
  --setenv ZAMMAD_DB zammad_production \
  --setenv ZAMMAD_DB_USER zammad \
  --setenv ZAMMAD_DB_PASS zammad \
  --setenv PGPORT 5433 \
  -- docker-entrypoint.sh postgres -p 5433
