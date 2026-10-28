# mart-position-snapshots

## Purpose

Defines the atomic transaction fact `fact_position_snapshot`: one row per de-duplicated observed position, loaded incrementally and idempotently from staging (and from raw for the columns staging never kept), keyed on event time, with every foreign key resolved.

## Requirements

### Requirement: One fact row per de-duplicated observed position

The system SHALL hold at most one `fact_position_snapshot` row per `(icao24, time_position)` pair, matching the staging de-duplication key, and SHALL load only accepted staging rows (never rejects).

#### Scenario: The same position reported by two overlapping polls
- **WHEN** two polls contain the same `icao24` at the same reported time and both reach staging
- **THEN** `fact_position_snapshot` holds exactly one row for that `(icao24, time_position)` pair

### Requirement: Positions are keyed on event time, not poll time

The system SHALL derive every date and time-of-day key of a position from `time_position` (the aircraft's own report time, event time), not from `fetched_at` (poll time). The poll time SHALL be retained on the row as lineage and for lag diagnostics.

#### Scenario: A stale position is placed by its report time
- **WHEN** a position's report time is well before the poll that delivered it
- **THEN** its date/time keys reflect the report time, and the poll time is still stored separately

### Requirement: Every foreign key is resolved, unmatched aircraft to the unknown member

The system SHALL set `aircraft_sk` by looking up `icao24` in `dim_aircraft` and using the unknown member (0) when there is no match, and SHALL keep `icao24` as a degenerate column on the fact because the unknown member hides the identity that segmentation needs.

#### Scenario: Position of an uncatalogued aircraft
- **WHEN** a position is loaded for an `icao24` absent from `dim_aircraft`
- **THEN** the row is written with `aircraft_sk = 0` and its real `icao24` preserved in the degenerate column

### Requirement: The position load is incremental and idempotent

The system SHALL process on each run only staging rows newer than the highest `raw_id` already in the fact (watermark derived from the fact itself, no external checkpoint), apply the load in one transaction, and leave the result unchanged when re-run on the same input.

#### Scenario: Re-running adds nothing
- **WHEN** the position load runs twice with no new staging rows in between
- **THEN** the second run inserts no rows and changes no existing row

#### Scenario: A missed run is caught up
- **WHEN** a scheduled run is skipped and the next run executes
- **THEN** the next run loads every staging row that accumulated since the last recorded watermark
