# Design

This document is the technical plan for the mart build. It is adapted from `DESIGN.md` (written with web Claude, delivered 2026-10-27) and the decisions in `PLANNING_LOG.md` (2026-10-21 and 2026-10-27). The requirements live in the spec deltas; this file covers how, not what. See `proposal.md` for why.

## Context

`staging.state_position` (accepted positions, de-duplicated on `(icao24, time_position)`), `staging.rejects`, and `staging.aircraft` (cleaned catalogue, 616,648 rows) exist and are loaded hourly on the VPS. `raw.state_snapshot` holds the original 17-element OpenSky state vectors as JSONB. The VPS is the single source of truth (PLANNING_LOG 2026-10-07); development is on the local dev database. `ingest.py` and `run_loop.py` are frozen.

Before writing SQL the implementer MUST map every column named here to the real source column (the spec names are targets; source names differ, e.g. staging `source_raw_id`, `baro_altitude`, `callsign_missing`). Where a source column assumed here does not exist, stop and ask — see `DESIGN.md` §0.

## Goals / Non-Goals

Goals: a Kimball star in `mart` that answers the dashboard's questions (daily curve, map, coverage) quickly and identically for everyone; the 600 s rule frozen into stored rows; loads that are incremental, idempotent and safe to re-run after a missed cycle.

Non-goals (design level): no airport dimension, no origin/destination inference, no manufacturer analysis, no real-time view (the transit fact lags live data by ≥ 10 min by design), no second region exercised (the structure allows it).

## Decisions

- **Surrogate keys for facts→dimensions, smart keys only for date/time.** `dim_date.date_sk = YYYYMMDD` and `dim_time_of_day.time_sk = hour*60+minute` are readable while debugging and let range filters prune; allowed only because these two are static and never versioned. `dim_aircraft` uses a sequence-issued surrogate key because the unknown member has no `icao24`, `000000` is a real catalogue row, and a surrogate key is what makes a later SCD2 switch possible without touching facts.
- **Keys from event time (`time_position`), not poll time (`fetched_at`).** A stale position keyed by poll time would land in the wrong minute/hour, and the stitching rule is defined on event time. Poll time is kept as lineage. [CONFIRM]
- **The mart load reads `raw.state_snapshot.payload` as well as `staging`.** Eight columns (`origin_country`, `last_contact_utc`, `velocity_mps`, `true_track_deg`, `vertical_rate_mps`, `geo_altitude_m`, `squawk`, `position_source`) and `snapshot_time` (`fetched_at`) were never kept by staging; re-running a 6.8M-row `UPDATE` on the live VPS is a bigger risk than this documented layering exception (PLANNING_LOG 2026-10-27). The join is on `source_raw_id`.
- **Transit fact is insert-only / closed-only**, so rows are never updated: a transit is inserted only once its last observation is > 600 s behind the live edge. Consequence: the fact lags live data by ≥ 10 min + the job interval. This removes the `is_closed` column and makes the exit keys `NOT NULL`. [CONFIRM]
- **Hourly coverage keeps two measures** (`distinct_polls` from `fetched_at`, `distinct_snapshots` from `api_time`); `is_fully_covered` uses `distinct_snapshots` against the 28 threshold to stay consistent with the spike and the hw5 test.
- **No manufacturer, no `built_year`/`engines`, `owner` stored but never displayed** — all measured as near-empty or privacy-sensitive for this traffic (PLANNING_LOG 2026-10-21, 2026-10-27).
- **Performance:** `SET LOCAL work_mem` inside the transit build; never CROSS JOIN candidate thresholds (forces a disk-spilling re-sort on the 4 GB VPS, PLANNING_LOG 2026-10-21). Gaps-and-islands via `LAG` + `SUM(new_flag) OVER …`, watermark derived from the target table (no checkpoint).
- **Units:** source units, unit in the column name (`_m`, `_mps`, `_deg`, `_km`, `_minutes`, `_s`); no ft/kn conversion in the warehouse. [CONFIRM]

## Reference DDL (PostgreSQL)

Physical types may be adjusted after inspecting the sources, but not the grain, keys, nullability or semantics without asking.

```sql
-- ===== Dimensions =====
CREATE TABLE mart.dim_date (
  date_sk                  INTEGER PRIMARY KEY,           -- YYYYMMDD
  full_date                DATE        NOT NULL UNIQUE,
  day_of_month             SMALLINT    NOT NULL,
  day_of_week_num          SMALLINT    NOT NULL CHECK (day_of_week_num BETWEEN 1 AND 7),
  day_name_en              VARCHAR(10) NOT NULL,
  day_name_hu              VARCHAR(10) NOT NULL,
  iso_week_year            SMALLINT    NOT NULL,
  week_of_year             SMALLINT    NOT NULL,
  month_num                SMALLINT    NOT NULL,
  month_name_en            VARCHAR(10) NOT NULL,
  month_name_hu            VARCHAR(12) NOT NULL,
  quarter                  SMALLINT    NOT NULL,
  year                     SMALLINT    NOT NULL,
  is_weekend               BOOLEAN     NOT NULL,
  is_holiday_hu            BOOLEAN     NOT NULL,
  season                   VARCHAR(10) NOT NULL,
  is_dst_local             BOOLEAN     NOT NULL,
  utc_offset_minutes_local SMALLINT    NOT NULL,
  is_dst_switch_day        BOOLEAN     NOT NULL
);

CREATE TABLE mart.dim_time_of_day (
  time_sk          INTEGER PRIMARY KEY CHECK (time_sk BETWEEN 0 AND 1439),
  hour_24          SMALLINT    NOT NULL,
  minute           SMALLINT    NOT NULL,
  quarter_hour     SMALLINT    NOT NULL,
  time_label       CHAR(5)     NOT NULL,
  hour_label       CHAR(5)     NOT NULL,
  time_of_day      VARCHAR(10) NOT NULL,
  time_of_day_hu   VARCHAR(10) NOT NULL,
  is_business_hour BOOLEAN     NOT NULL,
  is_peak_traffic  BOOLEAN     NOT NULL,  -- provisional 06-09/16-19; re-derive after build
  shift_label      VARCHAR(10) NOT NULL
);

CREATE TABLE mart.dim_region (
  region_sk          INTEGER PRIMARY KEY,
  region_code        VARCHAR(20)  NOT NULL,
  region_name_en     VARCHAR(100) NOT NULL,
  region_name_hu     VARCHAR(100) NOT NULL,
  bbox_min_latitude  NUMERIC(9,6) NOT NULL,
  bbox_max_latitude  NUMERIC(9,6) NOT NULL,
  bbox_min_longitude NUMERIC(9,6) NOT NULL,
  bbox_max_longitude NUMERIC(9,6) NOT NULL,
  bbox_area_km2      INTEGER      NOT NULL,
  valid_from         TIMESTAMPTZ  NOT NULL,
  valid_to           TIMESTAMPTZ,
  is_current         BOOLEAN      NOT NULL,
  UNIQUE (region_code, valid_from),
  CHECK (valid_to IS NULL OR valid_to > valid_from),
  CHECK ((valid_to IS NULL) = is_current)
);

CREATE SEQUENCE mart.dim_aircraft_sk_seq START 1;

CREATE TABLE mart.dim_aircraft (
  aircraft_sk          BIGINT PRIMARY KEY,               -- 0 = unknown member
  icao24               CHAR(6) UNIQUE,                   -- NULL only for unknown member
  registration         VARCHAR(20)  NOT NULL,
  type_designator      VARCHAR(10)  NOT NULL,
  model                VARCHAR(200) NOT NULL,
  aircraft_category    VARCHAR(100) NOT NULL,
  operator             VARCHAR(200) NOT NULL,
  operator_icao        VARCHAR(10)  NOT NULL,
  owner                VARCHAR(200) NOT NULL,             -- stored, NEVER displayed
  registration_country VARCHAR(100) NOT NULL,
  built_year           SMALLINT,                         -- dropped per 2026-10-27; keep NULL if column retained
  engines              VARCHAR(200) NOT NULL DEFAULT 'Unknown', -- dropped per 2026-10-27
  in_catalog           BOOLEAN      NOT NULL,
  loaded_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
  CHECK ((aircraft_sk = 0) = (NOT in_catalog)),
  CHECK ((aircraft_sk = 0) = (icao24 IS NULL))
);
-- NOTE: built_year and engines are dropped by decision (2026-10-27). Omit both
-- columns in the final DDL unless the implementer and user re-add them; shown
-- here struck through only to tie back to DESIGN.md. aircraft_category and owner
-- MUST be verified present in staging.aircraft (category_description, owner) or
-- added to staging.build_aircraft() first.

-- ===== Facts ===== (see DESIGN.md §6 / §9 for the full column list)
-- fact_position_snapshot: atomic, UNIQUE (icao24, time_position_utc), FKs to all
--   four dimensions (date/time twice: _utc and _local), degenerate icao24,
--   callsign, squawk, position_source, origin_country; measures latitude,
--   longitude, baro_altitude_m, geo_altitude_m, velocity_mps, true_track_deg,
--   vertical_rate_mps; quality flags from staging; raw_id (watermark), snapshot_time.
--   Indexes: date keys, aircraft_sk, raw_id, time_position_utc.
-- fact_flight_transit: aggregate, UNIQUE (icao24, first_seen_at),
--   CHECK (last_seen_at >= first_seen_at); entry/exit date keys (UTC+local),
--   entry time-of-day keys only; measures snapshot_count, duration_minutes,
--   distance_km, altitude/velocity min/max/avg; flags is_start_truncated,
--   is_end_truncated; segmentation_gap_s DEFAULT 600.
-- fact_hourly_coverage: UNIQUE (region_sk, hour_start_utc),
--   CHECK (time_of_day_sk % 60 = 0); distinct_polls, distinct_snapshots,
--   expected_polls (30), positions_landed, is_fully_covered, is_partial_hour.
```

The complete fact DDL is reproduced in `DESIGN.md` §9; the implementer uses it verbatim after the source-column mapping, applying the three deviations logged on 2026-10-27 (drop `built_year`/`engines`, add `distinct_snapshots`, read the raw-only columns from `raw`).

## Load order and scheduling

One-off (idempotent): `load_dim_date` (2020-01-01…2035-12-31), `load_dim_time_of_day` (1,440 rows), `load_dim_region` (bounds from `ingest.py`), `load_dim_aircraft` (insert unknown member if missing, then upsert by `icao24`, never truncate).

Hourly chain (extends `deploy/staging_ingest.sh`, minute 5, `flock`, one log line per step, stop on first error, alert on failure): `staging.ingest_snapshots` → `load_fact_position_snapshot` → `load_fact_flight_transit` → `load_fact_hourly_coverage`. `ops.check_freshness` runs as its own cron entry (minute 35) so it survives a failed or un-started chain; threshold 3 h of mart lag. Closing run `close_open_transits` once after collection ends.

Files: `sql/mart/00_dim_date.sql … 03_dim_aircraft.sql`, `10_fact_position_snapshot.sql … 12_fact_hourly_coverage.sql`, `sql/ops/freshness.sql`, `deploy/mart_build.sh`.

## [CONFIRM] items (implemented as the stated default; listed for veto before merge)

1. Keys from `time_position` (event time), poll time kept as lineage.
2. `registration_country` from catalogue `country`; API `origin_country` kept as a degenerate column on the atomic fact; `operator_country` dropped (no source).
3. Transit is insert-only/closed-only: `is_closed` removed, exit keys `NOT NULL`.
4. Units in metres/mps/deg, no ft/kn in the warehouse.
5. Transit `callsign` = most frequent non-empty callsign in the transit (ties: earliest).
6. `distance_km` = sum of haversine distances between consecutive positions where both are airborne (`on_ground = FALSE`).

## Risks / Trade-offs

- [Transit lags live data by ≥ 10 min] → by design (closed-only); acceptable, documented on the dashboard.
- [A late stale position within 600 s after a closed transit starts a new transit instead of extending it — 16 rows in the 2026-09-30 measurement] → no safety margin, documented limitation (PLANNING_LOG 2026-10-27).
- [Reading raw in the mart load couples the mart to the raw JSON layout] → the layout is fixed (17-element vector) and the collector is frozen; acceptable.
- [Big window sorts on the 4 GB VPS] → `SET LOCAL work_mem`, per-threshold passes, watermark-limited input.
- [Zero-aircraft polls are invisible] → the frozen collector writes nothing for an empty snapshot; stated as a limitation in `positions_landed`.
- [Rollback] → the mart is additive; `DROP SCHEMA mart CASCADE` (and the ops function) removes it entirely and it rebuilds from `raw`/`staging`. No raw or staging data is touched.

## Open Questions

Deferrable without changing the specs, the approach or the tasks:
- `is_peak_traffic` is provisional (06–09 / 16–19); re-derive it from the measured daily curve after the mart is loaded, with an `UPDATE` to `dim_time_of_day` (facts untouched). Also to be noted in the README as a future refinement.
- The README "Data provenance" line ("No personal data is involved") must be amended when this ships, because `owner` may contain personal names (stored but never displayed).
