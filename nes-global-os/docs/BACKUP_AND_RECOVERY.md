# Backup and Recovery

## What is backed up

The whole PostgreSQL database (all companies, people, agents, tasks, CRM, finance, reports, audit log, encrypted API keys),
as a compressed `pg_dump` custom-format archive, encrypted with AES-256 (PBKDF2, 200k iterations) using
`~/.nesos-backup-key`, plus a SHA-256 checksum file.

Since Milestone 2, uploaded Employee Hub documents are archived too (`nesos-files-*.tar.gz.enc`, same key).
To restore them:
```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass file:$HOME/.nesos-backup-key -in nesos-files-STAMP.tar.gz.enc \
  | docker compose exec -T api tar -C /data -xzf -
```

## Schedule

- Nightly 02:30 Asia/Karachi (cron, installed by `install.sh`) → `~/nesos-backups/`
- Retention: 14 days locally (`KEEP_DAYS`)
- Off-site: set `RCLONE_REMOTE` (e.g. `gdrive:nesos-backups`) after configuring `rclone config` — strongly recommended.
- The Command Centre's System health panel shows the last recorded backup time.

## Keys (store offline, separately)

| File | Needed for |
|---|---|
| `~/.nesos-backup-key` | Decrypting backups |
| `deploy/.env` (`NES_MASTER_KEY`) | Decrypting AI API keys and MFA seeds stored in the database |

## Restore

```bash
cd /opt/nes-global-os/deploy
./restore.sh ~/nesos-backups/nesos-20261109-0230.dump.enc
```
It verifies the checksum, asks you to type `RESTORE`, stops api + worker, restores, and restarts them.

## Disaster recovery (server lost)

1. New server → install Ubuntu → copy the project → restore `deploy/.env` from your offline copy.
2. `docker compose up -d db` then `./restore.sh <latest backup>` (copy the backup + `.nesos-backup-key` back first).
3. `docker compose up -d`. Users, MFA and AI keys keep working because `NES_MASTER_KEY` is the same.

## Tested

On 9 Nov 2026 a backup was taken, decrypted and restored into an empty database; the restored data matched
(8 companies, 114 agents, users intact) and the checksum verified. Repeat a test restore every month into a scratch
database (`PG_RESTORE_CMD` override) — an untested backup is not a backup.

## Targets

RPO (max data loss): 24 h now; < 5 min after Phase 2 (cloud primary with continuous WAL archiving).
RTO (time to recover): ~1 h with a spare machine and the offline keys.
