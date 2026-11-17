#!/usr/bin/env bash
# Encrypted PostgreSQL backup with rotation. Optional off-site copy with rclone (e.g. Google Drive / S3 / B2).
#   BACKUP_DIR (default ~/nesos-backups)   KEEP_DAYS (default 14)   RCLONE_REMOTE (e.g. gdrive:nesos-backups)
#   BACKUP_KEY_FILE (default ~/.nesos-backup-key)   PG_DUMP_CMD (override for non-Docker installs)
set -euo pipefail
cd "$(dirname "$0")"
BACKUP_DIR=${BACKUP_DIR:-$HOME/nesos-backups}
KEEP_DAYS=${KEEP_DAYS:-14}
KEY=${BACKUP_KEY_FILE:-$HOME/.nesos-backup-key}
PG_DUMP_CMD=${PG_DUMP_CMD:-"docker compose exec -T db pg_dump -U nesos -d nesos --format=custom"}
[ -s "$KEY" ] || { echo "Backup key $KEY missing"; exit 1; }
mkdir -p "$BACKUP_DIR"
STAMP=$(TZ=Asia/Karachi date +%Y%m%d-%H%M)
OUT="$BACKUP_DIR/nesos-$STAMP.dump.enc"
TMP="$OUT.partial"
# custom-format dump (compressed) → AES-256 (PBKDF2) encryption
$PG_DUMP_CMD | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$KEY" -out "$TMP"
[ -s "$TMP" ] || { echo "Backup produced no data"; rm -f "$TMP"; exit 1; }
mv "$TMP" "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
find "$BACKUP_DIR" -name 'nesos-*.dump.enc*' -mtime +"$KEEP_DAYS" -delete
# Uploaded documents (Employee Hub) live in a Docker volume: archive them alongside the database.
if [ -z "${SKIP_FILES:-}" ] && docker compose ps -q api >/dev/null 2>&1; then
  FOUT="$BACKUP_DIR/nesos-files-$STAMP.tar.gz.enc"
  docker compose exec -T api tar -C /data -czf - files 2>/dev/null \
    | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$KEY" -out "$FOUT" || rm -f "$FOUT"
  [ -f "$FOUT" ] && sha256sum "$FOUT" > "$FOUT.sha256"
  find "$BACKUP_DIR" -name 'nesos-files-*' -mtime +"$KEEP_DAYS" -delete
fi
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null; then
  rclone copy "$OUT" "$RCLONE_REMOTE" && rclone copy "$OUT.sha256" "$RCLONE_REMOTE"
fi
if [ -z "${SKIP_RECORD:-}" ]; then
  docker compose exec -T api python -m app.cli backup-recorded --file "$(basename "$OUT")" || true
fi
echo "Backup OK: $OUT ($(du -h "$OUT" | cut -f1))"
