# Spec Delta

## Purpose

Defines the aggregate fact `fact_flight_transit`: one row per continuous pass of an aircraft through the bounding box, with the 600 s segmentation rule frozen into stored rows, loaded insert-only and only for closed transits, with truncation flagged rather than dropped.

## ADDED Requirements

### Requirement: A transit groups observations at most 600 s apart

The system SHALL place two consecutive observations of the same `icao24` in the same transit when their `time_position` differs by at most 600 s, and SHALL start a new transit when the gap exceeds 600 s. Each row SHALL record the gap threshold used, so a future change of the rule is traceable. A transit is a pass through the box, not a flight, and SHALL never be labelled "flight".

#### Scenario: A gap at the threshold stays one transit
- **WHEN** one aircraft's consecutive positions are 600 s apart
- **THEN** they belong to the same transit row

#### Scenario: A gap over the threshold splits the transit
- **WHEN** one aircraft's consecutive positions are 601 s apart
- **THEN** they fall into two separate transit rows

#### Scenario: An uncatalogued aircraft still gets a transit
- **WHEN** a transit is built for an `icao24` absent from the catalogue
- **THEN** the transit row is written with `aircraft_sk = 0`, not dropped and not failing a foreign key

### Requirement: Only closed transits are inserted, and never updated

The system SHALL insert a transit only once its last observation is more than 600 s older than the newest observation in the position fact (the live edge), SHALL leave still-open transits for a later run, and SHALL never update a transit row after insert. A transit's natural key SHALL be `(icao24, first_seen_at)` so re-runs are idempotent.

#### Scenario: An open transit is held back
- **WHEN** an aircraft's latest observation is within 600 s of the live edge
- **THEN** no transit row is inserted for it yet

#### Scenario: The held-back transit is inserted once later
- **WHEN** more data arrives so the transit's last observation is now more than 600 s behind the live edge
- **THEN** the transit is inserted exactly once, and re-running the load does not insert a duplicate

### Requirement: A transit is counted on its entry day

The system SHALL key a transit by both entry and exit date (UTC and local) but SHALL count it, for daily totals, on its entry date, so a transit crossing midnight appears exactly once.

#### Scenario: A midnight-crossing transit
- **WHEN** a transit enters the box on one local day and leaves on the next
- **THEN** a daily transit count by entry date includes it on the entry day only

### Requirement: Truncated transits are kept and flagged

The system SHALL keep transits whose start or end is cut off by the edges of collection and SHALL flag them (`is_start_truncated`, `is_end_truncated`, never NULL) rather than dropping them, so counts include them while duration and distance statistics can exclude them. A one-off closing run after collection ends SHALL insert the remaining open transits with `is_end_truncated` set.

#### Scenario: Aircraft already airborne when collection began
- **WHEN** a transit's first observation is within 600 s of the collection start
- **THEN** the row is written with `is_start_truncated = TRUE` and still counted

#### Scenario: Closing run after collection ends
- **WHEN** the closing run executes after collection has stopped
- **THEN** every still-open transit is inserted with `is_end_truncated = TRUE`
