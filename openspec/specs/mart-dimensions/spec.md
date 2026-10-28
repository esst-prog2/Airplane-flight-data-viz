# mart-dimensions

## Purpose

Defines the four conformed dimensions of the mart star schema and the rules that keep facts joinable to them: surrogate-key stability, the unknown member, the never-NULL policy for dimension references and text attributes, and the explicit-timezone derivation of the date and time-of-day keys that every fact reuses.

## Requirements

### Requirement: Conformed dimensions shared by all facts

The system SHALL maintain exactly one `dim_aircraft`, one `dim_date`, one `dim_time_of_day` and one `dim_region`, referenced by every fact table, so that results from different facts are comparable and a correction is made in one place.

#### Scenario: Same aircraft, same key everywhere
- **WHEN** the same `icao24` appears in both the position fact and the transit fact
- **THEN** both reference the identical `aircraft_sk` value from the single `dim_aircraft`

#### Scenario: Dimensions exist before facts
- **WHEN** a fact load runs
- **THEN** every dimension row it references already exists, because dimensions are loaded before facts

### Requirement: Aircraft surrogate keys are stable for the life of the warehouse

The system SHALL assign an `aircraft_sk` to an `icao24` the first time it is loaded and SHALL never change or reassign it, even though `staging.aircraft` is rebuilt from scratch on each catalogue load. `dim_aircraft` SHALL be loaded by upsert on `icao24` (new `icao24` gets a new key from a sequence; existing `icao24` has its attributes overwritten) and SHALL never be truncated and rebuilt.

#### Scenario: Key survives a catalogue reload
- **WHEN** `load_dim_aircraft()` is run again after `staging.aircraft` has been rebuilt from a catalogue load
- **THEN** every `icao24` that already had an `aircraft_sk` keeps the same `aircraft_sk`, and existing fact rows still point at the same aircraft

#### Scenario: New aircraft gets a fresh key
- **WHEN** a catalogue load introduces an `icao24` not seen before and `load_dim_aircraft()` runs
- **THEN** that `icao24` receives a new, previously unused `aircraft_sk`

### Requirement: An unknown member absorbs unmatched references

`dim_aircraft` SHALL contain an unknown member with `aircraft_sk = 0`, `icao24` NULL, every text attribute set to `'Unknown'`, numeric attributes NULL, and `in_catalog = FALSE`. Every fact row whose observed `icao24` is absent from the catalogue SHALL reference `aircraft_sk = 0` rather than a NULL foreign key, so its traffic is still counted.

#### Scenario: Observed aircraft not in the catalogue
- **WHEN** a position or transit is loaded for an `icao24` that is not in `dim_aircraft`
- **THEN** the fact row's `aircraft_sk` is 0 (the unknown member) and the row is still written, not dropped

#### Scenario: Catalogue membership is distinguishable
- **WHEN** a query needs to separate "aircraft not in the catalogue" from "in the catalogue but attribute unknown"
- **THEN** `in_catalog = FALSE` identifies only the unknown member, while catalogue rows have `in_catalog = TRUE` with `'Unknown'` standing in for any missing text attribute

### Requirement: No dimension reference or text attribute is NULL

The system SHALL keep every fact foreign key `NOT NULL` (routing misses to an unknown member) and every dimension text attribute `NOT NULL` (using a sentinel such as `'Unknown'`). Numeric dimension attributes MAY be NULL when unknown, because a numeric sentinel would corrupt aggregates.

#### Scenario: A missing text attribute does not hide a row
- **WHEN** a catalogue field such as operator is empty for an aircraft
- **THEN** the dimension stores `'Unknown'`, so the row is not silently excluded from a `GROUP BY` or a `<>` filter

### Requirement: Date and time keys are derived with explicit time zones, UTC and local

The system SHALL key every fact event time twice against the conformed dimensions: once in UTC and once in `Europe/Budapest`, deriving the keys with explicit time zones and never the session time zone. `dim_date` SHALL carry the DST attributes (in-effect flag, UTC offset, switch-day flag) that distinguish days; `dim_time_of_day` SHALL hold one row per minute of a 24-hour day.

#### Scenario: The two keys differ across midnight
- **WHEN** an event occurs at a UTC instant that falls on a different calendar day in `Europe/Budapest`
- **THEN** its UTC date key and local date key point to two different `dim_date` rows

#### Scenario: The clock-change day is marked
- **WHEN** `dim_date` is generated over a range that includes a DST switch day such as 2026-10-25
- **THEN** that day's row has the switch-day flag set and the correct UTC offset

### Requirement: The region dimension records one region with SCD2 structure

`dim_region` SHALL hold the collection bounding box as a single current row with SCD2 validity columns (`valid_from`, `valid_to`, `is_current`), taking the box bounds from `ingest.py` without modifying that file. The structure supports a future region as additive rows without a schema change, even though it is not exercised now.

#### Scenario: The current region is resolvable
- **WHEN** a fact row is loaded for a position inside the bounding box
- **THEN** it references the one region row whose validity covers the event time and `is_current = TRUE`
