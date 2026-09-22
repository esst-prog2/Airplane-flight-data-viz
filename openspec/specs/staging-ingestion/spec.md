# staging-ingestion

## Purpose

Transforms raw, unvalidated OpenSky snapshots into a deduplicated, validated staging layer, separating records unusable for the project's purpose into a rejects table, without ever modifying the raw landing table or the collector that fills it.

## Requirements

### Requirement: Hard reject rules exclude structurally unusable records
The system SHALL exclude a raw record from staging and record it in `staging.rejects` with a reason, a reference to the source `raw.state_snapshot.id`, and a timestamp, when the record fails any of the following checks. The system SHALL continue processing and commit the remaining valid records in the same run rather than aborting.

#### Scenario: Missing icao24
- **WHEN** a raw record's icao24 field is null
- **THEN** the record is written to `staging.rejects` with reason `missing_icao24` and is not written to staging

#### Scenario: Missing position
- **WHEN** a raw record's latitude or longitude is null
- **THEN** the record is written to `staging.rejects` with reason `missing_position` and is not written to staging

#### Scenario: Missing time_position
- **WHEN** a raw record's time_position is null
- **THEN** the record is written to `staging.rejects` with reason `missing_time_position` and is not written to staging

#### Scenario: Impossible coordinate
- **WHEN** a raw record's latitude is outside [-90, 90], its longitude is outside [-180, 180], or its latitude and longitude are exactly (0, 0)
- **THEN** the record is written to `staging.rejects` with reason `impossible_coordinate` and is not written to staging

#### Scenario: A rejected record does not stop the run
- **WHEN** a batch of raw records being processed contains at least one record matching a reject rule and at least one valid record
- **THEN** the run completes, the rejected record is in `staging.rejects`, and the valid record is in `staging.state_position`

### Requirement: Usable-but-suspect records are kept and flagged
The system SHALL write a record to `staging.state_position` — not to `staging.rejects` — when it passes the hard reject rules, even if one of the following conditions holds, and SHALL mark which conditions applied.

#### Scenario: Missing altitude
- **WHEN** a valid raw record's baro_altitude is null
- **THEN** the record is written to `staging.state_position` with `altitude_missing` flagged

#### Scenario: Implausible altitude
- **WHEN** a valid raw record's baro_altitude is present and greater than 18,288 meters
- **THEN** the record is written to `staging.state_position` with `altitude_implausible` flagged

#### Scenario: Missing callsign
- **WHEN** a valid raw record's callsign is null
- **THEN** the record is written to `staging.state_position` with `callsign_missing` flagged

#### Scenario: Stale position
- **WHEN** a valid raw record's time_position is more than 1,800 seconds older than the poll's api_time
- **THEN** the record is written to `staging.state_position` with `position_stale` flagged

### Requirement: Overlapping polls of the same aircraft deduplicate
The system SHALL hold at most one `staging.state_position` row per distinct (icao24, time_position) pair, regardless of how many raw polls reported it.

#### Scenario: Same aircraft, same reported timestamp, two overlapping polls
- **WHEN** two raw polls whose time windows overlap both contain a record for the same icao24 with the same time_position
- **THEN** `staging.state_position` holds exactly one row for that (icao24, time_position) pair

### Requirement: The transform is idempotent and safe to re-run
The system SHALL determine, at the start of each run, the raw records not yet reflected in `staging.state_position` or `staging.rejects` without relying on any state outside those two tables, and SHALL leave no partial results if a run does not complete.

#### Scenario: Re-running over an already-processed range
- **WHEN** the transform is run twice with no new raw records landed in between
- **THEN** the second run adds no new rows to `staging.state_position` or `staging.rejects`

#### Scenario: A run that fails partway leaves no partial data
- **WHEN** the transform fails or is interrupted after processing some but not all of the new raw records in a run
- **THEN** none of that run's changes are visible in `staging.state_position` or `staging.rejects`, and the next run reprocesses the same raw records
