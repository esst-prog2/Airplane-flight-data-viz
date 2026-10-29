# Spec Delta

## Purpose

A read-only HTTP API that serves the mart's per-day aggregates to the dashboard, so the warehouse is never exposed directly and no caller can modify it.

## ADDED Requirements

### Requirement: The API only ever reads the warehouse

The API SHALL connect to the warehouse with a role that holds only `CONNECT`, `USAGE` and `SELECT`, and SHALL never issue a statement that modifies data or schema. A deployment MUST fail closed if given write-capable credentials is the only option — read access is a hard requirement, write access is never used.

#### Scenario: The database role cannot write
- **WHEN** the API is deployed with its configured database role
- **THEN** that role can run the API's `SELECT` queries and any `INSERT`, `UPDATE`, `DELETE` or `DDL` it attempted would be refused by the database

#### Scenario: No endpoint mutates state
- **WHEN** any API endpoint is called
- **THEN** the warehouse contents are unchanged afterwards

### Requirement: Per-day aggregate endpoints

The API SHALL expose, for a given local calendar day, the aggregates the dashboard renders: map bins, the daily traffic curve, hourly coverage, the aircraft type and country breakdown, and the headline KPIs. It SHALL also expose the range of local days for which data exists, so the date picker can offer only valid days.

#### Scenario: A day with data
- **WHEN** a caller requests the aggregates for a local day that has collected data
- **THEN** the API returns that day's map bins, hourly curve, coverage, type/country breakdown and KPIs

#### Scenario: A day with no data
- **WHEN** a caller requests a local day that has no collected data
- **THEN** the API returns empty or zeroed aggregates with a success status, not an error

#### Scenario: Available day range
- **WHEN** a caller requests the available date range
- **THEN** the API returns the earliest and latest local day for which the mart holds data

### Requirement: The API returns aggregates, never raw position rows

The API SHALL return pre-aggregated data (hexagonal map bins, per-hour counts, grouped breakdowns) and SHALL NOT return the individual position rows, so responses stay small regardless of how many positions a day holds.

#### Scenario: Map payload is binned
- **WHEN** the map endpoint is called for a busy day with ~170k positions
- **THEN** the response contains aggregated hexagon cells, not the ~170k individual points

### Requirement: The API never exposes personal data

The API SHALL NOT return the aircraft `owner` field in any response, because it can name a private individual. Type, operator-independent counts, and registration country are aggregate and non-personal and MAY be returned.

#### Scenario: Breakdown excludes owner
- **WHEN** the aircraft breakdown endpoint is called
- **THEN** the response contains type and country groupings and contains no `owner` value
