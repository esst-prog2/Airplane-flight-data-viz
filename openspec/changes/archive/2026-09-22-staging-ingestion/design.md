# Design

## Context

`raw.state_snapshot` (see proposal.md - Why) stores one row per aircraft per poll, with `payload` as a **positional JSON array**, not a keyed object — `ingest.py` writes `json.dumps(state)` straight from the OpenSky `/states/all` response. The field order (as of this design) is:

```
index  field
0      icao24
1      callsign
2      origin_country
3      time_position   (unix epoch seconds, nullable)
4      last_contact
5      longitude
6      latitude
7      baro_altitude    (meters, nullable)
8      on_ground
9      velocity
10     true_track
11     vertical_rate
12     sensors
13     geo_altitude
14     squawk
15     spi
16     position_source
```

All SQL in this change extracts fields by array index (`payload->>5`, etc.). This is an accepted risk, not an oversight: see Risks below.

Two thresholds in the spec (`altitude_implausible` at 18,288 m, `position_stale` at 1,800 s) were derived by querying the project's own 11-day, ~212k-row `raw.state_snapshot` on 2026-09-22:
- Staleness (`api_time - time_position`): p50 = 1s, p90 = 2s, p99 = 314s, p999 = 3138s, max = 9317s. 1,800s sits between p99 and p999 — past normal poll jitter, short of the extreme tail.
- Altitude (`baro_altitude`): legitimate traffic tops out around 14,333 m (multiple distinct aircraft); a single aircraft (icao24 `4bb86d`) reported an identical 27,706.32 m across four consecutive polls — a stuck-sensor signature, not real flight. 18,288 m (60,000 ft) sits above all observed legitimate traffic and below that outlier.

## Goals / Non-Goals

**Goals:**
- A SQL-only transform, callable repeatedly, that only ever reads `raw.state_snapshot` and only ever writes `staging.state_position` and `staging.rejects`.
- Correct behavior under repeated/partial runs (see spec's idempotency requirement).

**Non-Goals:**
- No change to `raw.state_snapshot`, `ingest.py`, or `run_loop.py` — see [[frozen-collector]] in project memory; this constraint is absolute for every change in this project.
- No aircraft/airport catalogue join, no flight-segment stitching, no star schema — those are later changes built on top of `staging.state_position`.
- No orchestration/scheduling of the transform (cron, CLI wrapper) — this change delivers the transform itself; how it gets invoked repeatedly is a separate concern.

## Decisions

**Watermark: derived, not stored.** Each run computes `GREATEST(COALESCE(MAX(source_raw_id) FROM staging.state_position, 0), COALESCE(MAX(source_raw_id) FROM staging.rejects, 0))` as the low-water mark and processes `raw.state_snapshot` rows with `id` above it. Considered a dedicated `ops.pipeline_checkpoint` table instead; rejected because it introduces a second piece of state that can desync from what was actually committed, where the derived value cannot — it is definitionally in sync with what is visible in the two output tables.

**Atomicity: one run, one transaction.** The whole read-validate-write cycle for a run happens in a single transaction. If it fails or is interrupted, nothing commits, and because the watermark is derived from committed rows, the next run naturally reprocesses the same range. This is what makes the derived-watermark approach safe.

**Dedup via upsert, not read-then-check.** `staging.state_position` has a unique constraint on `(icao24, time_position)`; the insert uses `ON CONFLICT (icao24, time_position) DO NOTHING`. Simpler and safer under concurrent or repeated runs than a separate existence check.

**Rejects live in `staging`, not `raw`.** `staging.rejects` is the output of this transform, not part of the immutable landing layer — keeping it in `staging` keeps `raw` a pure, untouched mirror of what the collector wrote.

**Table/column naming**: `staging.state_position` (columns: `source_raw_id`, `icao24`, `callsign`, `time_position` as `timestamptz`, `latitude`, `longitude`, `baro_altitude`, `on_ground`, `altitude_missing` bool, `altitude_implausible` bool, `callsign_missing` bool, `position_stale` bool) and `staging.rejects` (columns: `source_raw_id`, `reason`, `rejected_at`). `reason` uses a `CHECK` constraint against the four known values rather than a free-text column, so a typo or new rule fails loudly instead of silently fragmenting the rejects table.

## Risks / Trade-offs

- **[Risk]** Positional JSON indexing breaks silently if OpenSky ever reorders the `/states/all` response fields → **Mitigation**: none automated in this change (out of scope); the risk is accepted because `raw.state_snapshot` is preserved untouched, so a future fix can simply re-run this transform with corrected indices.
- **[Risk]** Measured thresholds (18,288 m / 1,800 s) reflect only 11 days of Central European traffic and could shift as more data arrives → **Mitigation**: thresholds are named constants in one place in the SQL, not scattered; revisiting them later is cheap.
- **[Trade-off]** No dedicated checkpoint table makes the pipeline simpler and self-consistent, but means "how far did we get" is only answerable by querying `staging.state_position`/`staging.rejects` directly, not by reading a single status row.

## Migration Plan

Purely additive: creates two new tables and a transform in the `staging` schema. No existing table is altered, no data is migrated, no rollback beyond dropping the new objects is needed.
