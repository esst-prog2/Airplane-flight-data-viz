# Spec Delta

## Purpose

Provides a single `flights` command-line interface that drives the whole pipeline —
collecting, staging, and building the warehouse — from one documented entry point,
so the project can be run and demonstrated without knowing its internal file layout.

## ADDED Requirements

### Requirement: Single command entry point with subcommands

The system SHALL provide a `flights` command that exposes the pipeline operations as
subcommands (`ingest`, `build`, `run`). Running `flights` with no subcommand, or with
`--help`, SHALL print usage listing the available subcommands; each subcommand SHALL
provide its own `--help`. An unknown subcommand or invalid option SHALL exit non-zero
with an error message.

#### Scenario: Top-level help lists the subcommands

- **WHEN** a user runs `flights --help`
- **THEN** the output lists the `ingest`, `build`, and `run` subcommands
- **AND** the command exits zero

#### Scenario: Unknown subcommand is rejected

- **WHEN** a user runs `flights frobnicate`
- **THEN** the command exits non-zero with an error naming the problem
- **AND** no pipeline work is performed

### Requirement: Ingest a single poll and report what was landed and refused

The `flights ingest --once` subcommand SHALL fetch one snapshot over the configured
bounding box and land it into the raw table using the existing collector, then run the
staging ingest over the pending raw data. It SHALL print the number of raw records
landed and, from staging, the number accepted and the number rejected broken down by
reject reason. If the fetch or the database operation fails, the command SHALL exit
non-zero and SHALL NOT report success.

#### Scenario: One poll is landed and summarised

- **WHEN** a user runs `flights ingest --once` against a reachable API and database
- **THEN** one raw snapshot is landed and the staging ingest runs over the pending raw data
- **AND** the output reports the raw records landed and the accepted and rejected counts
- **AND** the rejected count is broken down by reason
- **AND** the command exits zero

#### Scenario: A failed fetch is reported as failure

- **WHEN** `flights ingest --once` cannot fetch a snapshot or reach the database
- **THEN** the command exits non-zero with an error
- **AND** it does not report a successful ingest

### Requirement: Build the warehouse from the staged data

The `flights build` subcommand SHALL run the staging ingest followed by the mart fact
loads (position snapshots, flight transits, and hourly coverage) in dependency order,
the same sequence the scheduled build runs. With the `--with-dims` option it SHALL load
the four mart dimensions before the fact loads, for a build against an empty warehouse.
It SHALL print a per-step result count and a short summary of the current warehouse state,
including the number of flight segments over the last 24 hours and the share of them
matched to a known aircraft type. Each step is incremental and idempotent, so running
`build` after `ingest` SHALL NOT reprocess already-loaded data. If any step fails, the
command SHALL stop at that step and exit non-zero.

#### Scenario: A default build runs the staging and fact loads

- **WHEN** a user runs `flights build` against a warehouse whose dimensions already exist
- **THEN** the staging ingest and the three fact loads run in dependency order
- **AND** the output reports a count for each step
- **AND** the output includes a summary with the last-24-hour segment count and the share matched to a known aircraft type
- **AND** the command exits zero

#### Scenario: A from-empty build loads the dimensions first

- **WHEN** a user runs `flights build --with-dims`
- **THEN** the four mart dimensions are loaded before the fact loads run

#### Scenario: A failing step stops the build

- **WHEN** a step of `flights build` fails
- **THEN** the build stops at that step
- **AND** the command exits non-zero with an error identifying the failed step

### Requirement: Start the continuous collector

The `flights run` subcommand SHALL start the continuous collection loop, polling on the
collector's fixed interval until interrupted. Interrupting it (for example with Ctrl-C)
SHALL stop collection and return control to the shell.

#### Scenario: Continuous collection starts

- **WHEN** a user runs `flights run`
- **THEN** the continuous collector starts and polls on its fixed interval
- **AND** it keeps running until the user interrupts it
