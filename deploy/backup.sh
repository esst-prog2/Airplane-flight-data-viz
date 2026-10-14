#!/usr/bin/env bash
# Nightly pg_dump of the flights database, run on the VPS via cron.
# Keeps the last 14 dumps; older ones are rotated out.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/root/backups/flights}"
KEEP="${KEEP:-14}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="$BACKUP_DIR/flights_${TIMESTAMP}.dump"

cd "$REPO_DIR"
# Dump to a temp name and rename only on success, so a failed pg_dump never
# leaves a truncated flights_*.dump that rotation would count as a good backup.
trap 'rm -f "$DUMP_FILE.partial"' EXIT
docker compose exec -T postgres pg_dump -U flights -Fc flights > "$DUMP_FILE.partial"
mv "$DUMP_FILE.partial" "$DUMP_FILE"

echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  wrote $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# Rotate: keep only the newest $KEEP dumps.
ls -1t "$BACKUP_DIR"/flights_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm --
