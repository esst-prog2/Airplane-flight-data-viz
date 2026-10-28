# VPS cron and deploy steps

All database writes run on the VPS (`ssh root@65.21.0.244`, repo at `/root/flights`,
Postgres reachable only via `docker compose exec -T postgres psql ...`). The collector
(`ingest.py` / `run_loop.py`) is frozen and runs in its own container; nothing here
touches it.

## One-off, in order

```bash
cd /root/flights
git fetch upstream && git merge --ff-only upstream/main

# 1. apply the schema and functions (idempotent: CREATE ... IF NOT EXISTS / OR REPLACE)
for f in sql/mart/*.sql sql/ops/*.sql; do
    docker compose exec -T postgres psql -U flights -d flights -v ON_ERROR_STOP=1 < "$f"
done

# 2. load the dimensions once (and again only after a new catalogue load)
bash deploy/mart_dims.sh

# 3. first fact build by hand, to measure it before trusting the cron
bash deploy/mart_build.sh
```

## Crontab

Edit with `crontab -e`. Replace the old standalone staging line with the mart build
chain (the chain runs the staging ingest as its first step, so staging must not also
run on its own — otherwise two jobs write staging in parallel).

```
# REMOVE this old line (staging now runs inside the mart chain):
# 5 * * * * /root/flights/deploy/staging_ingest.sh >> /root/backups/flights/staging.log 2>&1

# hourly mart build chain: staging -> position -> transit -> coverage
5 * * * * /root/flights/deploy/mart_build.sh >> /root/backups/flights/mart_build.log 2>&1

# freshness watch, independent of the chain so it fires even when the chain failed
35 * * * * /root/flights/deploy/mart_freshness.sh >> /root/backups/flights/mart_freshness.log 2>&1

# nightly backup (unchanged)
17 3 * * * /root/flights/deploy/backup.sh >> /root/backups/flights/backup.log 2>&1
```

Check with `crontab -l`. The two mart logs each get one line per run; a failed build
step and a stale mart both alert the webhook (`ALERT_WEBHOOK_URL` in `.env`). The
freshness threshold defaults to 180 minutes (`MART_FRESHNESS_THRESHOLD_MINUTES`).

## Collection end (one-off, late November 2026)

```bash
# close the transits still open at the end of collection, flagged is_end_truncated
docker compose exec -T postgres psql -U flights -d flights -c "SELECT mart.close_open_transits();"
```
