#!/usr/bin/env bash
# Go back to the version that ran before the last ./scripts/deploy.sh.
#
# deploy.sh keeps that version's images as :previous. This makes them the
# current (:latest) images again and restarts the services without building.
#
# Usage (from the repo root on the server, same arguments as deploy.sh):
#   ./scripts/rollback.sh
#   ./scripts/rollback.sh -f docker-compose.yml
#
# Note: only the code goes back. A database migration run by the new version
# is not undone; check with the team before rolling back across one.
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose "$@")

mapfile -t built_images < <("${compose[@]}" config --images | grep -v '[/:]' | sort -u)

for image in "${built_images[@]}"; do
  if ! docker image inspect "${image}:previous" >/dev/null 2>&1; then
    echo "No ${image}:previous image: nothing to roll back to (deploy with ./scripts/deploy.sh first)." >&2
    exit 1
  fi
done

echo "== Restoring the previous version"
for image in "${built_images[@]}"; do
  docker tag "${image}:previous" "${image}:latest"
  echo "   ${image}:previous -> ${image}:latest"
done

"${compose[@]}" up -d --no-build
echo "== Rolled back. Running containers:"
"${compose[@]}" ps
