# Proposal

## Why

Right now the only data in the warehouse is `raw.state_snapshot`: every OpenSky poll landed as an unvalidated JSONB array, duplicates and all. Nothing downstream (star schema, dashboard) can be built on that safely — bad records (missing identity, missing position, physically impossible values) and duplicate snapshots from overlapping polls need to be separated out before anything else can trust the data. This change builds that first transformation: a rejects table for unusable records and a staging table of cleaned, deduplicated, typed rows, derived entirely in SQL from `raw.state_snapshot` — without touching the collector that produces it.

## What Changes

- Add a `staging.state_position` table: one row per (icao24, time_position), typed and deduplicated from `raw.state_snapshot`. Overlapping polls carrying the same aircraft at the same reported timestamp collapse to a single row.
- Add a `staging.rejects` table: one row per raw record that fails a hard validity rule, with a `reason` and a reference back to the source `raw.state_snapshot.id`.
- Add a SQL transform (function or script) that reads new rows from `raw.state_snapshot`, applies the four reject rules, applies the flag conditions, upserts into `staging.state_position`, inserts into `staging.rejects`, and is safe to re-run repeatedly: a run that fails partway commits nothing, and a run over an already-processed range produces no duplicates. The range to process is derived each run from `MAX(raw_id)` already present across `staging.state_position` and `staging.rejects` — no separate checkpoint table.
- **BREAKING**: none — purely additive; `raw.state_snapshot` and the collector are unchanged.

Four hard reject rules (raw record is unusable for the project's purpose, so it is excluded entirely):
- `missing_icao24` — icao24 is null
- `missing_position` — latitude or longitude is null
- `missing_time_position` — time_position is null
- `impossible_coordinate` — latitude outside [-90, 90], longitude outside [-180, 180], or exactly (0, 0)

Flag conditions (record is still usable — kept in staging, marked):
- `altitude_missing` — baro_altitude is null (normal for a grounded aircraft)
- `altitude_implausible` — baro_altitude present but above 18,288 m, a threshold measured from this project's own collected data (see design.md)
- `callsign_missing` — callsign is null
- `position_stale` — time_position more than 1,800 s older than the poll's `api_time`, a threshold measured from this project's own collected data (see design.md)

Fields left untouched regardless of nullability: velocity, true_track, vertical_rate, squawk, sensors.

## Capabilities

### New Capabilities
- `staging-ingestion`: transforming raw OpenSky snapshots into a deduplicated, validated staging table plus a rejects table, via a repeatable SQL transform.

### Modified Capabilities
None.

## Impact

- New SQL: `staging.state_position` table, `staging.rejects` table, and the transform that populates them (exact form — function vs. script — decided in design.md).
- No changes to `ingest.py`, `run_loop.py`, `raw.state_snapshot`, or any other existing table.
- Out of scope for this change: aircraft/airport catalogue resolution, flight-segment stitching, the star schema, and the dashboard. Those depend on this staging layer but are separate future changes.
