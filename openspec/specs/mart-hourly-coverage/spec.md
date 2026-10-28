# mart-hourly-coverage

## Purpose

Defines the periodic snapshot fact `fact_hourly_coverage`: one row per UTC hour of the whole collection, including hours with zero polls, recording how well the collector covered each hour so that gaps are visible rather than silent and the dashboard can explain a notch in the traffic curve.

## Requirements

### Requirement: Every collection hour has a row, generated from the calendar

The system SHALL produce one row per UTC hour from the first collection hour up to the last completed hour, generating the hours from the calendar so that an hour with zero polls still has a row (raw has no row for such an hour, which is exactly what must be made visible). The current, incomplete hour SHALL never be stored. The load SHALL be incremental and idempotent on `(region_sk, hour_start_utc)`.

#### Scenario: An hour with no polls
- **WHEN** no poll landed in a given completed UTC hour
- **THEN** that hour still has a coverage row, with a zero poll count

#### Scenario: The current hour is excluded
- **WHEN** the load runs partway through an hour
- **THEN** no row is written for that still-incomplete hour

### Requirement: Coverage records two poll measures and an api_time-based full-cover flag

The system SHALL store, per hour, the number of distinct `fetched_at` polls (did the collector run) and the number of distinct `api_time` snapshots (did we receive new API data), and SHALL set the fully-covered flag from the distinct `api_time` count against the 28 threshold, so the meaning of a fully covered hour stays consistent with the earlier spike, the 99.70% figure and the hw5 test.

#### Scenario: Collector ran but the API repeated a snapshot
- **WHEN** an hour has 30 distinct `fetched_at` polls but fewer distinct `api_time` snapshots
- **THEN** both counts are stored, and the fully-covered flag is decided by the `api_time` count

#### Scenario: Under-covered hour is flagged
- **WHEN** an hour has fewer than 28 distinct `api_time` snapshots
- **THEN** its row has the fully-covered flag false

### Requirement: The first and last collection hours are marked partial

The system SHALL mark only the very first and very last calendar hour of the whole collection as partial and exclude those two from coverage percentages, and SHALL NOT mark the early intermittent hours as partial, because those are real low-coverage gaps the table exists to show.

#### Scenario: Structurally partial edge hour
- **WHEN** the first collection hour began part-way through the clock hour
- **THEN** its row is marked partial and left out of coverage-percentage calculations

#### Scenario: A real early gap is not hidden
- **WHEN** an early hour had few polls because the collector was not yet running continuously
- **THEN** its row is not marked partial and its low coverage remains visible
