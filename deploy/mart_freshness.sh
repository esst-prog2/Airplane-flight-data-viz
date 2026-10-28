#!/usr/bin/env bash
# Freshness watch, run by its own cron entry on the VPS, independent of the build chain
# so it still fires when the chain has failed or did not start. Reports how far the mart
# lags raw and alerts the webhook when the lag exceeds the threshold (default 3 hours).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_DIR"

# make .env values (ALERT_WEBHOOK_URL) available when started from cron, which
# does not read .env; harmless when run by hand with the var already exported.
[ -f .env ] && { set -a; . ./.env; set +a; }
WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"
THRESHOLD="${MART_FRESHNESS_THRESHOLD_MINUTES:-180}"

row="$(docker compose exec -T postgres psql -U flights -d flights -At -F '|' \
        -c "SELECT coalesce(lag_minutes::text, 'n/a'), is_stale FROM ops.check_freshness(${THRESHOLD});")"
lag="${row%%|*}"
stale="${row##*|}"

echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  mart lag ${lag} min  stale=${stale}  threshold=${THRESHOLD}min"

if [ "$stale" = "t" ] && [ -n "$WEBHOOK_URL" ]; then
    curl -fsS -m 10 -X POST -H 'Content-Type: application/json' \
         -d "{\"content\": \"mart is stale: ${lag} min behind raw (threshold ${THRESHOLD} min)\"}" \
         "$WEBHOOK_URL" >/dev/null 2>&1 || true
fi
