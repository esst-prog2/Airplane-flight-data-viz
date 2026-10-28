#!/usr/bin/env bash
# One-off (and safe to re-run) load of the four mart dimensions. Run once after applying
# the mart SQL, and again only after a new aircraft catalogue is loaded (load_dim_aircraft
# upserts by icao24 and never rebuilds, so surrogate keys stay stable). Not on the hourly
# cron: the fact chain (mart_build.sh) assumes the dimensions already exist.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

run() {
    local label="$1" sql="$2"
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC')  ${label}: $(
        docker compose exec -T postgres psql -U flights -d flights -v ON_ERROR_STOP=1 -At -c "$sql"
    )"
}

run dim_date     "SELECT mart.load_dim_date();"
run dim_time     "SELECT mart.load_dim_time_of_day();"
run dim_region   "SELECT mart.load_dim_region();"
run dim_aircraft "SELECT * FROM mart.load_dim_aircraft();"
