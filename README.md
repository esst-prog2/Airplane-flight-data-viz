# Airplane-flight-data-viz

Central European air traffic: building a history the API does not keep

The OpenSky Network API tells you what is in the air right now. It does not tell you what was in the air last Tuesday. This project polls that live feed on a schedule, lands every snapshot, stitches the snapshots into flights, and turns them into a queryable warehouse — so questions about traffic patterns over time in this region can be asked at all.

## Status

What actually runs today, as opposed to the target shape described in [Vision](#vision) below.

**Built and running:**
- **Collector** (`ingest.py` + `run_loop.py`) — polls the OpenSky `/states/all` endpoint every 120s over the Central European bounding box, handles OAuth2 client-credentials auth, and lands every snapshot into `raw.state_snapshot` as raw, unvalidated JSON. Survives a failed run and alerts a webhook after 3 consecutive failures.

  These two files are complete and **frozen**: the collector is the project's one irreversible part — a day not collected is a day of history that can never be backfilled — so no change in this project modifies `ingest.py` or `run_loop.py`.

  Runs on a Hetzner VPS since 2026-09-17, not the development machine. An early spike ([sql/spike/collector_coverage.sql](sql/spike/collector_coverage.sql)) measured only 6.82% hourly coverage, then a later check measured 5.92% — both numbers turned out to be artifacts of querying the local dev machine's intermittent Postgres container instead of the VPS (see PLANNING_LOG.md, 2026-10-07 correction entry). Re-measured directly against the VPS for the same style of 14-day window: **99.70%** of hours (336 of 337) had ≥28 polls — the collector has in fact been running continuously. The hourly data-quality / collection-coverage table is still worth building (as a permanent record of this, and to catch real future outages), but it is not fixing an active problem.
- **Infrastructure** — Postgres + the collector run via `docker compose up -d` on the VPS (two containers, `root@65.21.0.244`, repo at `/root/flights`). The database schemas `raw`, `staging`, `mart`, and `ops` exist on the VPS, and the staging tables and both functions below are deployed there too. `staging.ingest_snapshots()` runs hourly as the first step of the mart build chain ([deploy/mart_build.sh](deploy/mart_build.sh), minute 5), which replaced the standalone staging cron on 2026-10-28; the backlog of 1,202,981 raw rows was processed by hand on 2026-10-14 (56 s, 1,150,190 accepted, 0 rejected, the rest duplicates). Nightly `pg_dump` backups run via cron ([deploy/backup.sh](deploy/backup.sh)), kept on the VPS and mirrored to the developer's machine.

**Built and deployed on the VPS** (staging runs hourly from cron since 2026-10-14):
- **Staging layer, rejects table and deduplication** — [sql/init/03_staging.sql](sql/init/03_staging.sql) and [sql/transform/staging_ingest.sql](sql/transform/staging_ingest.sql) (`staging.ingest_snapshots()`): four hard reject rules into `staging.rejects`, four soft flags on `staging.state_position`, one row per `(icao24, time_position)`. The cron job calls it hourly; you can also call it by hand.
- **Hourly collection coverage** — [sql/quality/hourly_coverage.sql](sql/quality/hourly_coverage.sql) (`staging.hourly_coverage()`): a callable function that counts hours with ≥28 polls. The stored hourly version now exists in the mart as `fact_hourly_coverage` (see below); this function remains for ad-hoc checks.
- **Automated tests** — [tests/test_hourly_coverage.py](tests/test_hourly_coverage.py) checks the coverage function against the real database (`DATABASE_URL`); [tests/test_staging_ingest.py](tests/test_staging_ingest.py) checks the reject rule, deduplication and re-run safety of `staging.ingest_snapshots()` on invented data in a throwaway database on the local dev Postgres (refuses to run against any other host). Install with `pip install -r requirements-dev.txt`, run with `pytest`. The third behaviour under [How we would know it works](#4-how-we-would-know-it-works) (unknown aircraft resolves to an unknown dimension member) is now tested in [tests/test_mart_facts.py](tests/test_mart_facts.py), since the aircraft dimension and its unknown member now exist.

**Built, deployed on the VPS, and measured:**
- **Aircraft catalogue** — OpenSky's complete aircraft database (`aircraft-database-complete-2025-08.csv`, 616,675 aircraft; the "daily" `aircraftDatabase.csv` is incomplete according to OpenSky's own README, and the newest complete dump is from 2025-08, so aircraft registered since then are missing). [scripts/load_aircraft_catalog.py](scripts/load_aircraft_catalog.py) lands the file unchanged in `raw.aircraft_catalog` ([sql/init/04_aircraft_catalog.sql](sql/init/04_aircraft_catalog.sql)); `staging.build_aircraft()` ([sql/transform/aircraft_build.sql](sql/transform/aircraft_build.sql)) cleans it into `staging.aircraft`, skipping the 27 ids that are not 6 hex digits instead of guessing; `staging.aircraft_catalog_coverage()` ([sql/quality/aircraft_catalog_coverage.sql](sql/quality/aircraft_catalog_coverage.sql)) measures how much observed traffic the catalogue can describe. Tests: [tests/test_aircraft_catalog.py](tests/test_aircraft_catalog.py). The source file is not in git (`data/` is ignored).
- **Measured coverage** — on the VPS, over the 14 days to 2026-10-14 (12,210 aircraft, 2,366,510 positions): **82.3%** of aircraft are in the catalogue and **80.7%** have a type code; by positions it is **87.6%** and **86.8%**. The gap between the two views means the unmatched aircraft (2,157 of them, about 136 positions each against about 206 for matched ones) are the occasional visitors, not the regulars. The catalogue is from 2025-08, so aircraft registered since then are missing and these figures are a lower bound. Operator is the weak field: on the VPS (same 14 days) it is known for **26.7%** of aircraft (3,257 of 12,208) and **33.5%** of positions (792,362 of 2,365,861); among aircraft that are in the catalogue it is 32% (3,257 of 10,053). The catalogue itself has it for only 5.2% of its rows. So type and country analysis is solid, operator analysis covers roughly one third of the traffic and should be presented as such.

**Built, deployed on the VPS, and running hourly** (the Kimball star schema, since 2026-10-28):
- **Dimensions** — `mart.dim_date` (5,844 days), `mart.dim_time_of_day` (1,440 minutes), `mart.dim_region` (the single Central European box), and `mart.dim_aircraft` (616,648 rows including the unknown member, built from `staging.aircraft`). Loaded by [deploy/mart_dims.sh](deploy/mart_dims.sh), which is safe to re-run and never rebuilds surrogate keys. SQL in [sql/mart/](sql/mart/).
- **Facts** — `mart.fact_position_snapshot` (atomic, one row per aircraft per poll: 6,960,020 rows at first build), `mart.fact_flight_transit` (aggregate, one row per stitched transit at a 600 s gap threshold: 393,878 rows), and `mart.fact_hourly_coverage` (one row per region-hour, the stored data-quality table: 994 rows). Every load is incremental and idempotent — a watermark derived from the target table plus `ON CONFLICT` — so a missed run is caught up by the next.
- **Freshness check** — `ops.check_freshness()` ([sql/ops/freshness.sql](sql/ops/freshness.sql)) reports how far the mart lags the raw landing table; stale past 180 minutes (one missed hourly run).
- **Automation** — the hourly chain [deploy/mart_build.sh](deploy/mart_build.sh) runs the staging ingest and then the three fact loads in dependency order (cron, minute 5), replacing the old standalone staging cron; [deploy/mart_freshness.sh](deploy/mart_freshness.sh) watches the lag independently (minute 35). Both alert the webhook on a failed step or a stale mart. The first full historical build ran by hand on 2026-10-28.
- **Tests** — [tests/test_mart_dimensions.py](tests/test_mart_dimensions.py), [tests/test_mart_facts.py](tests/test_mart_facts.py), and [tests/test_ops_freshness.py](tests/test_ops_freshness.py) against throwaway databases on the local dev Postgres.

**Not yet built** (see [Vision](#vision) for the target shape):
- Map dashboard and daily traffic curve — there is no dashboard container or code yet
- A `flights` CLI (`flights ingest --once`, `flights build`) — today you run `python ingest.py` or `python run_loop.py` directly, and the mart is built by the deploy scripts above
- Airport catalogue ingestion (OurAirports) — deliberately deferred; the aircraft catalogue comes first

**Next step:** the map dashboard and daily traffic curve over the mart. One provisional choice to revisit then: `is_peak_traffic` in `dim_time_of_day` is currently a placeholder (06:00–09:00 / 16:00–19:00 local); re-derive it from the measured daily traffic curve once the dashboard surfaces one (PLANNING_LOG.md, 2026-10-21).

## Vision

This section describes the target shape of the finished project — the demo, the scope, and the risks — not what is running today. See [Status](#status) above for that.

### 1. The demo

I open a terminal and run docker compose up -d. Three containers start: Postgres, the collector, and the dashboard. I run flights ingest --once. It fetches the current air picture over the Central European bounding box, writes 480 raw aircraft states, and prints what it refused: 12 records with no position, 3 with an altitude above 60,000 ft, all of them in the rejects table with a reason. I run flights build. It rebuilds the star schema and prints 1,240 flight segments over the last 24 hours, 89% of them matched to a known aircraft type. I open localhost:8501, pick yesterday, and the map shows traffic density as 3D hexagons over the region. The daily curve has a visible notch between 03:00 and 04:00 — the collector was down for an hour, and the same gap is in the data-quality table underneath.

### 2. The shape

    in           the OpenSky /states/all endpoint, one snapshot per poll,
                 bounded to a fixed Central European box

    out          a star schema of flight segments in Postgres, an hourly
                 data-quality table, and a map dashboard over both

    in between   land each snapshot raw and unvalidated; clean, type and
                 de-duplicate it; stitch consecutive snapshots of the same
                 aircraft into flight segments; join to aircraft and
                 airport catalogues

### 3. The size

The first useful version does this, and does it with a single day of collected data:

- polls the API on a schedule and lands raw snapshots without losing a run to a malformed response or an HTTP error
- rejects bad records into a separate table with a reason instead of failing
- builds a cleaned staging layer and a normalised star schema with real keys
- stitches position snapshots into flight segments
- records hourly collection coverage so gaps are visible rather than silent
- serves a map and a daily traffic curve from the warehouse

It explicitly does not do this term:

- no prediction of anything — no delay model, no ETA, no ML layer
- no inference of origin and destination airports from the track
- no real-time view; resolution is the poll interval, and the dashboard reads batch tables
- no second region and no change to the bounding box once collection starts
- no backfill of any period before day one, because the API does not offer it
- no public write access, no user accounts, no Kubernetes

The warehouse is useful after one day. Every additional week makes the seasonal questions answerable, but nothing in the first version depends on the weeks arriving.

### 4. How we would know it works

Three behaviours a test could check:

- Given a snapshot in which an aircraft record has a null latitude or longitude, that record lands in the rejects table with reason missing_position and the run still completes and commits the remaining records.
- Given two polls whose time windows overlap and which both contain the same aircraft at the same reported timestamp, the staging table holds one row for it, not two.
- Given an aircraft whose 24-bit address is absent from the aircraft catalogue, the flight segment is still created and resolves to the unknown member of the aircraft dimension, rather than failing on the foreign key.

### 5. What could stop this

**No backfill.** Every week of history costs a week of wall-clock time. If collection starts late or dies silently, that period is gone. Mitigated by starting collection in week three and alerting after three consecutive failed runs.

**API access.** OpenSky moved to OAuth2 client credentials in March 2026. Access is free for non-commercial and research use but metered by a daily credit budget, and the terms could change mid-term. The raw landing table is the hedge: once a snapshot is stored it is mine regardless.

**Unknown catalogue coverage.** The share of aircraft addresses that resolve to a known type and operator is not known until measured. If it is low, the operator and fleet analysis weakens. It gets measured in week four and reported as a number either way.

**No ground truth for segmentation.** There is no label saying where one flight ends and the next begins; the rule is mine to define and defend. Spot checks against public flight-tracking sites, and the rule stated explicitly rather than buried.

**Techniques not yet attempted:** TLS behind a reverse proxy and a workflow orchestrator. Running Docker Compose on a rented server is done (Hetzner VPS, since 2026-09-17) — each of the others is still a first for me.

### Data provenance

OpenSky Network state vectors, free for non-commercial and research use. Aircraft metadata from the same source; airport reference data from OurAirports, public domain. Aircraft registrations are public records. One field needs care: OpenSky's `owner` can name a private individual for a small aircraft, so `dim_aircraft` stores `owner` but the dashboard never displays it — only aggregate type, operator and country are shown. No other personal data is involved, so everything can be shown in class.

## Setup

Secrets are not in the repository. Copy `.env.example` to `.env`
and fill in your own values:

    cp .env.example .env

You need an OpenSky account and an API client
(Account page -> create API client) for the credentials.

Then, to start what is actually built today — Postgres and the collector:

    docker compose up -d

There is no dashboard container and no `flights` CLI yet (see [Status](#status)); the collector starts polling immediately and writes to `raw.state_snapshot`.
