# pipeline-freshness

## Purpose

Defines how the mart loads are scheduled as one chain and how the pipeline's freshness is watched, so that a stalled or failed load is noticed before the presentation rather than discovered on the day.

## Requirements

### Requirement: The mart loads run as one ordered chain after staging

The system SHALL run the staging ingest, then the mart fact loads in dependency order (positions, then transits, then hourly coverage) as a single scheduled chain guarded against overlap, with each step in its own transaction, logging one line per step, and stopping the chain on the first failing step.

#### Scenario: Load order is honoured
- **WHEN** the chain runs
- **THEN** dimensions already exist and facts are loaded after staging, positions before transits

#### Scenario: A failing step stops the chain and alerts
- **WHEN** a step in the chain fails
- **THEN** the chain stops before the later steps and an alert is sent through the existing webhook

### Requirement: Freshness is checked independently of the build chain

The system SHALL provide a freshness check that reports how far the mart lags raw (newest raw `fetched_at` minus the newest position-fact arrival) and alerts when the lag exceeds a configured threshold. The check SHALL run as its own scheduled entry, independent of the build chain, so it still runs when the chain has failed or did not start.

#### Scenario: Lag within the threshold
- **WHEN** the mart's newest data is within the freshness threshold of raw
- **THEN** the check reports healthy and sends no alert

#### Scenario: Lag exceeds the threshold
- **WHEN** the mart lags raw by more than the threshold (for example after two missed runs)
- **THEN** the check sends an alert through the existing webhook

#### Scenario: The chain stalled entirely
- **WHEN** the build chain has not run at all for longer than the threshold
- **THEN** the independent freshness check still runs and alerts
