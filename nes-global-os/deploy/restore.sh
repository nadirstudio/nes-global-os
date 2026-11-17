#!/usr/bin/env bash
# Restore an encrypted backup:  ./restore.sh ~/nesos-backups/nesos-YYYYMMDD-HHMM.dump.enc
# DESTRUCTIVE: replaces the current database. Stops api + worker while restoring.
set -euo pipefail
cd "$(dirname "$0")"
FILE=${1:?usage: restore.sh <backup.dump.enc>}
KEY=${BACKUP_KEY_FILE:-$HOME/.nesos-backup-key}
PG_RESTORE_CMD=${PG_RESTORE_CMD:-"docker compose exec -T db pg_restore -U nesos -d nesos --clean --if-exists --no-owner"}
[ -f "$FILE.sha256" ] && sha256sum -c "$FILE.sha256"
read -rp "This will REPLACE the live database with $(basename "$FILE"). Type RESTORE to continue: " ok
[ "$ok" = "RESTORE" ] || { echo "Cancelled"; exit 1; }
[ -n "${NO_STOP:-}" ] || docker compose stop api worker
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$KEY" -in "$FILE" | $PG_RESTORE_CMD
[ -n "${NO_STOP:-}" ] || docker compose start api worker
echo "Restore complete."
