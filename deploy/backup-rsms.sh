#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/rsms}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
ENV_FILE="${ENV_FILE:-/etc/rsms/rsms.env}"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/rsms_${STAMP}.dump"
# pg_dump expects a libpq URI, while SQLAlchemy commonly uses postgresql+psycopg://.
PG_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
pg_dump --format=custom --no-owner --no-acl --dbname="$PG_URL" --file="$OUT"
chmod 600 "$OUT"
find "$BACKUP_DIR" -type f -name 'rsms_*.dump' -mtime "+$RETENTION_DAYS" -delete
printf 'Backup created: %s\n' "$OUT"
