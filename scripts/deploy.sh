#!/usr/bin/env bash
# Deploy the latest code on a server, keeping only the previous version's
# images for a quick rollback and freeing the disk of everything older.
#
# Why: every `docker compose up -d --build` left the old images and build
# cache behind. On staging they filled the 29 GB disk, and meeting recordings
# could no longer be saved (Bug-49).
#
# Usage (from the repo root on the server, after `git pull`):
#   ./scripts/deploy.sh                       # same files as `docker compose up`
#   ./scripts/deploy.sh -f docker-compose.yml # or name the compose files
# Roll back to the previous version with ./scripts/rollback.sh (same arguments).
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose "$@")

# Images built from this repo (core-api, ai-core, frontend). Pulled images
# such as postgres:15-alpine or minio/minio have a "/" or ":" in their name.
mapfile -t built_images < <("${compose[@]}" config --images | grep -v '[/:]' | sort -u)
if [ "${#built_images[@]}" -eq 0 ]; then
  echo "No locally built images found in the compose config; nothing to deploy." >&2
  exit 1
fi

echo "== Disk before deploy"
df -h / | tail -1

echo "== 1. Keep the running version as :previous (for rollback)"
for image in "${built_images[@]}"; do
  if docker image inspect "${image}:latest" >/dev/null 2>&1; then
    docker tag "${image}:latest" "${image}:previous"
    echo "   ${image}:latest -> ${image}:previous"
  fi
done

echo "== 2. Build and start the new version"
"${compose[@]}" up -d --build

echo "== 3. Delete everything older than :previous"
# Images with no name left: the version before :previous, and other leftovers.
docker image prune -f
# Build cache not used by the images we keep. The next build re-downloads
# Python/npm packages, so it is a little slower; the disk stays clean.
docker builder prune -f

echo "== Done. Disk after deploy"
df -h / | tail -1
docker system df
