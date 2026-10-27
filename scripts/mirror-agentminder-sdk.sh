#!/usr/bin/env bash
# Mirror Broadcom's AgentMinder Python SDK into a private GitHub package.
#
#   scripts/mirror-agentminder-sdk.sh <SDK download or wheel> <build>
#   scripts/mirror-agentminder-sdk.sh ~/Downloads/agentminder-sdk-4.1.1.tar.gz 4.1.1.1673
#
# The SDK is not on public PyPI, and the workflow runner cannot reach
# Broadcom's registry with a token that lasts. So the wheel is kept in
# ghcr.io/modern-apps-5/agentminder-sdk, a private package. The image is
# FROM scratch and holds only the wheel; nothing runs it. Workflows pull it
# with GITHUB_TOKEN through the registry API, because the runner has no
# Docker.
#
# <build> is AgentMinder's full build, such as 4.1.1.1673. The image gets
# that tag and the release tag, 4.1.1. Run this when AgentMinder is
# upgraded, with the SDK from the same release.
#
# Needs docker and gh, with gh logged in with the write:packages scope.
# A new package is private. Give the-goad read access to it once: package
# settings, Manage Actions access.
set -euo pipefail

SRC=${1:?usage: $0 <SDK download (.tar.gz/.tgz/.zip) or wheel> <build, such as 4.1.1.1673>}
BUILD=${2:?usage: $0 <SDK download or wheel> <build, such as 4.1.1.1673>}
IMAGE=ghcr.io/modern-apps-5/agentminder-sdk

[[ $BUILD =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.[0-9]+$ ]] || { echo "build must look like 4.1.1.1673" >&2; exit 1; }
RELEASE=${BASH_REMATCH[1]}

WORK=$(mktemp -d)
trap 'docker logout ghcr.io >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT
export DOCKER_CONFIG=$WORK/docker
mkdir -p "$WORK/ctx" "$WORK/src" "$DOCKER_CONFIG"

# Accept the wheel itself, or the SDK download that holds it.
case $SRC in
  *.whl)          cp "$SRC" "$WORK/src/" ;;
  *.tar.gz|*.tgz) tar xzf "$SRC" -C "$WORK/src" 2>/dev/null ;;
  *.zip)          unzip -q "$SRC" -d "$WORK/src" ;;
  *) echo "$SRC: expected a .whl, .tar.gz, .tgz or .zip" >&2; exit 1 ;;
esac
mapfile -t WHEELS < <(find "$WORK/src" -name 'agentminder-*.whl')
[[ ${#WHEELS[@]} -eq 1 ]] || { echo "expected one agentminder-*.whl in $SRC, found ${#WHEELS[@]}" >&2; exit 1; }
WHEEL=$(basename "${WHEELS[0]}")
cp "${WHEELS[0]}" "$WORK/ctx/"

cat > "$WORK/ctx/Dockerfile" <<EOF
FROM scratch
LABEL org.opencontainers.image.source="https://github.com/modern-apps-5/the-goad" \\
      org.opencontainers.image.description="AgentMinder Python SDK $BUILD, wheel only. Private, for the-goad workflows." \\
      org.opencontainers.image.version="$BUILD"
COPY $WHEEL /
EOF

# No attestations: a plain manifest keeps the workflow's pull one lookup.
docker build -q --provenance=false --sbom=false -t "$IMAGE:$BUILD" -t "$IMAGE:$RELEASE" "$WORK/ctx" >/dev/null
gh auth token | docker login ghcr.io -u "$(gh api user -q .login)" --password-stdin >/dev/null
docker push -q "$IMAGE:$BUILD"
docker push -q "$IMAGE:$RELEASE"

echo "pushed $WHEEL as $IMAGE:$BUILD and :$RELEASE"
echo "sha256 $(sha256sum "$WORK/ctx/$WHEEL" | cut -d' ' -f1)"
