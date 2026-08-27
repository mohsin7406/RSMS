#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /path/to/backup.dump postgresql://user:pass@host:5432/restore_database" >&2
  exit 2
fi
BACKUP="$1"
TARGET_URL="$2"
TARGET_URL="${TARGET_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
[[ -f "$BACKUP" ]] || { echo "Backup not found: $BACKUP" >&2; exit 1; }

# The target database must already exist. Never point this at the live RSMS database.
pg_restore --clean --if-exists --no-owner --no-acl --exit-on-error --dbname="$TARGET_URL" "$BACKUP"
echo "Restore completed successfully. Run RSMS against this restore database and execute the test/smoke checklist before declaring backups verified."
