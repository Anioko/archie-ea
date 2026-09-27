#!/usr/bin/env bash
# Thin operator wrapper for the digest-only production deployer.
# Usage: scripts/deploy.sh <ghcr-image@sha256:digest> <full-commit> [--yes]
set -euo pipefail

DROPLET=${DROPLET:-root@134.122.105.56}
APP_DIR=${APP_DIR:-/root/archie-ea}
SSH_OPTS=(-o ConnectTimeout=20 -o BatchMode=yes)
IMAGE_REF=${1:-}
EXPECTED_COMMIT=${2:-}
ASSUME_YES=${3:-}

die() { printf 'deploy: %s\n' "$*" >&2; exit 1; }

[[ "$IMAGE_REF" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || \
    die "first argument must be an immutable GHCR digest reference"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || \
    die "second argument must be a full 40-character Git SHA"
[[ "$ASSUME_YES" = "" || "$ASSUME_YES" = "--yes" ]] || die "unknown argument: $ASSUME_YES"

if [ "$ASSUME_YES" != "--yes" ]; then
    printf 'Deploy %s\nfor commit %s\nto %s? [y/N] ' "$IMAGE_REF" "$EXPECTED_COMMIT" "$DROPLET"
    read -r answer
    [[ "$answer" =~ ^([yY]|yes|YES)$ ]] || die "aborted"
fi

# The checkout supplies only the versioned Compose/control-plane files. The
# production overlay removes all /app source mounts, and deploy/deploy.sh uses
# --no-build, so runtime bytes still come exclusively from IMAGE_REF.
ssh "${SSH_OPTS[@]}" "$DROPLET" bash -s -- "$APP_DIR" "$IMAGE_REF" "$EXPECTED_COMMIT" <<'REMOTE'
set -euo pipefail
APP_DIR=$1
IMAGE_REF=$2
EXPECTED_COMMIT=$3

cd "$APP_DIR"
git fetch --prune origin
LEGACY_COMMIT=$(git rev-parse HEAD)
git checkout --detach "$EXPECTED_COMMIT"
./deploy/remote-cutover.sh "$IMAGE_REF" "$EXPECTED_COMMIT" "$LEGACY_COMMIT"
REMOTE
