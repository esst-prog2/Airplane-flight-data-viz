# Proposal

## Why

The collector lands raw snapshots and `staging` cleans and de-duplicates them, but every analytical question still has to parse the staging rows, re-implement the 600 s segmentation rule, and look up the aircraft catalogue itself — slowly, and each query slightly differently, so two people counting "flights" get two numbers. The dashboard the project is presented with in early December 2026 (daily traffic curve, map, coverage) has no stable source. This change builds the `mart` star schema that does that work once, in one place, so every query and the dashboard return the same answer, and the segmentation rule is frozen into stored rows rather than re-invented in each `WHERE` clause.

The full design, its measurements and every decision are in `DESIGN.md` (this change's `design.md` is adapted from it) and `PLANNING_LOG.md` (2026-10-21 and 2026-10-27).

## What Changes

- Four conformed dimensions in `mart`: `dim_aircraft` (SCD1, surrogate key, stable keys, unknown member, no manufacturer, `owner` stored but never displayed), `dim_date` (one row per day, UTC/local distinction carried by the fact keys plus DST attributes), `dim_time_of_day` (one row per minute), `dim_region` (one-row SCD2 structure, deliberately kept for a possible future region).
- Three fact tables sharing those dimensions: `fact_position_snapshot` (atomic, one row per de-duplicated observed position), `fact_flight_transit` (aggregate, one row per continuous transit through the box at a 600 s gap threshold, insert-only / closed-only, truncation flags), `fact_hourly_coverage` (periodic snapshot, one row per UTC hour including zero-poll hours, two poll measures).
- Incremental, idempotent load functions for every table, chained after the existing hourly staging job in one cron entry; a one-off closing run after collection ends.
- A freshness check in `ops`, run as its own cron entry, alerting via the existing webhook when the mart lags raw by more than a threshold.
- Tests (pytest against a throwaway local database, as the existing tests) for the behaviours each capability states.
- The mart load reads `raw.state_snapshot.payload` as well as `staging` for the columns staging never kept (a documented layering exception, PLANNING_LOG 2026-10-27).

Not changed: `ingest.py`, `run_loop.py` (frozen); `raw` and `staging` tables and their load functions; no airport dimension, no origin/destination inference, no prediction, no manufacturer analysis, no second region exercised.

## Capabilities

### New Capabilities
- `mart-dimensions`: generating and loading the four conformed dimensions, with surrogate-key stability, the unknown member, the never-NULL policy, and the explicit-timezone date/time key derivation rules every fact reuses.
- `mart-position-snapshots`: the atomic position fact — incremental idempotent load from staging and raw, event-time keys, foreign-key resolution to the unknown member, one row per `(icao24, time_position)`.
- `mart-flight-transits`: the aggregate transit fact — the 600 s segmentation rule, closed-only insert-only loading, truncation flags, counting a transit on its entry day, the closing run.
- `mart-hourly-coverage`: the periodic coverage fact — calendar-generated hours including zero-poll hours, the two poll measures and the `api_time`-based full-cover flag, the partial-hour rule.
- `pipeline-freshness`: the `ops` freshness check and the scheduled chain — load order, one transaction per step, alert on lag and on step failure.

### Modified Capabilities
<!-- none: the mart reads staging but changes no staging requirement -->

## Impact

- New SQL under `sql/mart/` and `sql/ops/`, new `mart.*` and `ops.*` database objects, a new `deploy/mart_build.sh`, and additions to the VPS crontab. New tests under `tests/`.
- No change to `raw`/`staging` schemas, to the collector, or to any existing load function. The mart is additive and can be dropped and rebuilt from `raw`/`staging` without data loss.
- Several decisions carry **[CONFIRM]** marks in `design.md` (implemented as their stated defaults, listed there for veto before merge).
