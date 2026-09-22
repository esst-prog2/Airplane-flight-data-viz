# Tasks

## 1. Staging schema

- [x] 1.1 Add `sql/init/03_staging.sql` creating `staging.state_position` (unique constraint on `(icao24, time_position)`, columns per design.md) and verify with `docker exec flights_db psql -U flights -d flights -c '\d staging.state_position'`
- [x] 1.2 In the same file, create `staging.rejects` with a `CHECK` constraint restricting `reason` to the four defined values, and verify with `\d staging.rejects`
- [x] 1.3 Apply `03_staging.sql` to the already-running `flights_db` container (it only auto-runs on a fresh volume) and verify both tables exist with `\dt staging.*`

## 2. Transform

- [x] 2.1 Write the SQL transform (`sql/transform/staging_ingest.sql` or a SQL function) implementing: derived watermark from `MAX(source_raw_id)` across both staging tables, the four reject rules, the four flag conditions, upsert into `staging.state_position` with `ON CONFLICT (icao24, time_position) DO NOTHING`, insert into `staging.rejects`, all in one transaction
- [x] 2.2 Run it once against the live `raw.state_snapshot` data and verify: every raw row in the processed range lands in exactly one of `staging.state_position` or `staging.rejects`, and row counts reconcile (rejects + distinct staging keys accounts for the processed raw rows, duplicates collapsing as expected)

## 3. Verify against spec scenarios

- [x] 3.1 For each of the four reject rules (`missing_icao24`, `missing_position`, `missing_time_position`, `impossible_coordinate`), find or construct a matching raw row and verify it lands in `staging.rejects` with the correct `reason`, and that other rows in the same run still commit
- [x] 3.2 For each of the four flags (`altitude_missing`, `altitude_implausible`, `callsign_missing`, `position_stale`), find or construct a matching raw row and verify it lands in `staging.state_position` with the correct flag set
- [x] 3.3 Find (or construct via a duplicate insert into `raw.state_snapshot`) two overlapping-poll rows for the same `icao24` and `time_position`, and verify `staging.state_position` holds exactly one row for that pair
- [x] 3.4 Re-run the transform with no new raw rows and verify zero rows are added to either staging table
- [x] 3.5 Interrupt or force-fail the transform mid-run (e.g. inject an error before `COMMIT`) and verify no partial rows appear in either staging table, then verify a normal re-run afterward processes the full range correctly
