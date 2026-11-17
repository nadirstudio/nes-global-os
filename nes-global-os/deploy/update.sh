#!/usr/bin/env bash
# Update NES GLOBAL OS from a new release zip, keeping your settings (.env), database and uploaded files.
#   cd /opt/nes-global-os/deploy
#   ./update.sh ~/nes-global-os-v1.1.zip
set -euo pipefail
cd "$(dirname "$0")"
ZIP=${1:?usage: ./update.sh <release.zip>}
ROOT=$(cd .. && pwd)
command -v rsync >/dev/null || sudo apt-get install -y rsync unzip >/dev/null

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP"
SRC="$TMP/nes-global-os"
[ -d "$SRC/backend" ] && [ -f "$SRC/deploy/docker-compose.yml" ] || { echo "This is not an NES GLOBAL OS release zip."; exit 1; }

echo "==> Safety backup before updating"
./backup.sh

echo "==> Copying new version (your deploy/.env is kept)"
rsync -a --delete \
  --exclude 'deploy/.env' --exclude '**/node_modules' --exclude 'frontend/out' --exclude 'frontend/.next' \
  --exclude 'mobile/dist' "$SRC/" "$ROOT/"
chmod +x "$ROOT"/deploy/*.sh
grep -q '^NES_CORS_ORIGINS=' .env || echo 'NES_CORS_ORIGINS=https://localhost' >> .env

echo "==> Rebuilding and restarting (database migrations run automatically)"
docker compose up -d --build

echo "==> Waiting for the API"
for i in $(seq 1 60); do
  docker compose exec -T api python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')" 2>/dev/null && break
  sleep 3
done
docker compose exec -T api python -m app.cli seed
docker compose ps
echo "==> Update complete."
