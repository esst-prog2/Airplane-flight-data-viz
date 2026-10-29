# Spec Delta

## Purpose

Deliver the dashboard in two forms from one codebase — a live version while collection runs and a permanent public version from a frozen snapshot — both reading the mart read-only and showing no personal data.

## ADDED Requirements

### Requirement: The live form reflects current data

The live dashboard SHALL run where it can reach the warehouse and SHALL show data no more than roughly one build interval stale (the mart is rebuilt hourly). It SHALL read through the read-only API, and MAY fall back to reading the database directly when the API is unavailable.

#### Scenario: Recent data appears
- **WHEN** an hourly mart build has completed and the viewer opens or refreshes the live dashboard
- **THEN** the most recent completed day is selectable and its views render

#### Scenario: API fallback
- **WHEN** the read-only API is unreachable but the database is
- **THEN** the live dashboard can still render by reading the database directly

### Requirement: The permanent offline form needs no live database and no login

The project SHALL provide a permanent, publicly reachable version of the dashboard, served from a frozen snapshot of the final data, that requires no login and no running warehouse. It serves both as a presentation backup and as a portfolio artifact reachable from the repository.

#### Scenario: Open with no credentials
- **WHEN** anyone opens the public offline URL without signing in
- **THEN** the dashboard renders its views from the frozen snapshot with no live database involved

### Requirement: One codebase, a pluggable data source

The dashboard SHALL obtain its data through a single data-source interface with interchangeable backends — the read-only API, a direct database connection, and the frozen snapshot — so the views behave identically regardless of which backend is active.

#### Scenario: Swapping the backend does not change the views
- **WHEN** the same dashboard build runs against the API, against the database directly, and against the frozen snapshot
- **THEN** each produces the same views, differing only in how current the data is

### Requirement: The frozen snapshot stores aggregates, not raw positions

The frozen snapshot SHALL contain the per-day aggregates the views need (map bins, hourly curve, coverage, type/country breakdown, KPIs) and SHALL NOT contain the raw position rows, so it stays small enough to host on a static/free platform.

#### Scenario: Snapshot excludes raw positions
- **WHEN** the snapshot is built from the final dump
- **THEN** it holds the aggregated view data and does not carry the millions of individual position rows

### Requirement: No form writes to the warehouse or exposes personal data

No form of the dashboard SHALL write to the warehouse, and no form SHALL display or ship the aircraft `owner` field. The live form reads through a read-only role; the offline form reads a read-only snapshot that was built without the `owner` field.

#### Scenario: Read-only live access
- **WHEN** the live form reads data
- **THEN** it uses a role with no write privilege and the warehouse is unchanged

#### Scenario: Snapshot carries no owner
- **WHEN** the frozen snapshot is built
- **THEN** it contains no `owner` values
