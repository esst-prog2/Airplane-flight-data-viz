# Tasks

## 1. Source mapping and schema

- [ ] 1.1 Map every target column in design.md to the real source column in `staging.state_position`, `staging.aircraft`, `raw.state_snapshot` and `ingest.py` (bbox); verify by listing the live columns and confirm `aircraft_category` (`category_description`) and `owner` exist in `staging.aircraft`, otherwise stop and ask before proceeding
- [ ] 1.2 Write `sql/mart/00_dim_date.sql`, `01_dim_time_of_day.sql`, `02_dim_region.sql`, `03_dim_aircraft.sql` DDL (tables, sequence, CHECK constraints) per design.md, dropping `built_year`/`engines`; verify by applying them to the local dev database with no error and `\d mart.*` showing the constraints
- [ ] 1.3 Write `sql/mart/10_fact_position_snapshot.sql`, `11_fact_flight_transit.sql`, `12_fact_hourly_coverage.sql` DDL (tables, FKs, unique/natural keys, indexes); verify they apply cleanly and every FK is `NOT NULL`

## 2. Dimension loads

- [ ] 2.1 Implement `mart.load_dim_date()` (2020-01-01…2035-12-31, DST attributes via explicit `Europe/Budapest`); verify a spot-check row (e.g. 2026-10-25 is a switch day, correct offset) and that re-running inserts nothing
- [ ] 2.2 Implement `mart.load_dim_time_of_day()` (1,440 rows, labels, provisional `is_peak_traffic`); verify row count is 1,440 and `time_sk = hour*60+minute`
- [ ] 2.3 Implement `mart.load_dim_region()` reading the bbox constants from `ingest.py` (do not retype); verify the one row matches `ingest.py` and `is_current = TRUE`
- [ ] 2.4 Implement `mart.load_dim_aircraft()` (unknown member sk 0; upsert by `icao24`, never truncate); verify re-running after a catalogue reload keeps every existing `icao24 → aircraft_sk` (test 9) and the unknown member exists

## 3. Fact loads

- [ ] 3.1 Implement `mart.load_fact_position_snapshot()` (incremental by `raw_id` watermark; join `staging` + `raw` payload for the raw-only columns; event-time keys UTC+local; `aircraft_sk` via `icao24`→unknown member; one transaction; `ON CONFLICT (icao24, time_position_utc) DO NOTHING`); verify dedup (test 2), unknown-member resolution (test 1) and idempotency (test 4)
- [ ] 3.2 Implement `mart.load_fact_flight_transit()` (gaps-and-islands at 600 s via `LAG`+`SUM OVER`; closed-only at `live_edge − 600 s`; entry/exit keys; truncation flags; `SET LOCAL work_mem`; `ON CONFLICT (icao24, first_seen_at)`); verify the 600/601 s split (test 3), closed-only hold-then-insert (test 5), entry-day counting (test 6) and idempotency
- [ ] 3.3 Implement `mart.close_open_transits()` (closing run: remaining open islands inserted with `is_end_truncated = TRUE`); verify on a fixture that an open transit is inserted once with the flag set
- [ ] 3.4 Implement `mart.load_fact_hourly_coverage()` (calendar-generated completed hours; `distinct_polls` from `fetched_at`, `distinct_snapshots` from `api_time`; `is_fully_covered` on `api_time ≥ 28`; first/last hour `is_partial_hour`; current hour excluded); verify a zero-poll hour still gets a row (test 8)

## 4. Scheduling and freshness

- [ ] 4.1 Write `deploy/mart_build.sh` chaining `staging.ingest_snapshots` → the three fact loads, `flock`, one log line per step, stop and alert via the webhook on the first failure; verify a forced step failure stops the chain and would alert
- [ ] 4.2 Implement `ops.check_freshness()` (mart lag = newest raw `fetched_at` − newest position-fact arrival; alert over 3 h); verify it reports healthy within threshold and alerts past it on a fixture
- [ ] 4.3 Document the two VPS crontab entries (build chain at minute 5, freshness at minute 35) in the deploy docs; verify the lines are correct and non-overlapping (do not install here — that is a VPS step the user runs)

## 5. Tests

- [ ] 5.1 Add `tests/test_mart_dimensions.py` covering dimension stability, unknown member, no-NULL policy and DST keys (tests 7, 9, 10) on a throwaway local database via the existing `conftest.py` fixture; verify green and red-checked
- [ ] 5.2 Add `tests/test_mart_facts.py` covering position dedup/idempotency, transit segmentation/closed-only/midnight, and coverage zero-poll (tests 1–6, 8); verify green and red-checked
- [ ] 5.3 Add a regression test against a fixed historical window (transit count at 600 s in the agreed window and tolerance, order of magnitude of the logged 17,272 / 2 days, test 11); verify green

## 6. Deploy and documentation

- [ ] 6.1 Apply the DDL and load functions to the VPS, run the dimension loads and the first fact loads by hand (user runs the VPS writes), measure and log the real row counts and timing in `PLANNING_LOG.md`; verify counts are sane against the live traffic
- [ ] 6.2 Update `README.md`: move the built mart items from "Not yet built", amend the "Data provenance" line about `owner`, and add the `is_peak_traffic` re-derivation as a future refinement; verify the status section matches what is deployed
- [ ] 6.3 Confirm the [CONFIRM] items in design.md with the user before merge; log any change in `PLANNING_LOG.md`
