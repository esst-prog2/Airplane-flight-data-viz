# Spec Delta

## Purpose

The five dashboard views and the date-picker interaction that let a viewer explore one day of collected Central European air traffic, presenting partial or missing data honestly.

## ADDED Requirements

### Requirement: A date picker drives every view

The dashboard SHALL let the viewer choose one local calendar day, and every view SHALL reflect that day. On first load it SHALL default to the most recent local day that has data. The picker SHALL offer only days within the available data range.

#### Scenario: Selecting a day updates all views
- **WHEN** the viewer picks a different local day
- **THEN** the map, the daily curve, the coverage view, the type/country breakdown and the per-day figures all refresh to that day

#### Scenario: Default day on load
- **WHEN** the dashboard is opened with no day chosen
- **THEN** it shows the most recent local day that has collected data

### Requirement: Traffic-density map

The dashboard SHALL show a map of the selected day's air traffic over the collection bounding box, with positions aggregated into hexagonal bins so density is visible without plotting every point.

#### Scenario: Density is visible
- **WHEN** a day with heavy traffic is selected
- **THEN** the map shows denser / taller hexagon bins where more positions were observed

### Requirement: Daily traffic curve

The dashboard SHALL show, for the selected day, the number of distinct aircraft present per local hour (a 24-point curve in `Europe/Budapest` local time).

#### Scenario: Hourly local curve
- **WHEN** a day is selected
- **THEN** the curve shows one value per local hour from 00:00 to 23:00, measuring distinct aircraft present in that hour

### Requirement: Coverage view makes collector gaps visible

The dashboard SHALL show, for the selected day, which hours were fully covered and which were not, from `fact_hourly_coverage`, so a collector outage appears as a visible gap rather than being silently absent from the other views.

#### Scenario: A day with an outage
- **WHEN** a day in which the collector missed one or more hours is selected
- **THEN** the coverage view marks those hours as not fully covered

### Requirement: Aircraft type and country breakdown

The dashboard SHALL show, for the selected day, a breakdown of observed traffic by aircraft type and by registration country. It SHALL NOT show an operator breakdown, and SHALL NOT display the `owner` field.

#### Scenario: Breakdown content
- **WHEN** a day is selected
- **THEN** the breakdown lists counts by aircraft type and by country, with no operator breakdown and no owner shown

### Requirement: KPI header band

The dashboard SHALL show a header band of headline totals for the whole collected dataset: total positions, total transits, distinct aircraft observed, days collected, and the catalogue coverage share.

#### Scenario: KPIs render
- **WHEN** the dashboard is open
- **THEN** the header band shows the dataset-wide totals above the per-day views

### Requirement: Partial and incomplete data is labelled honestly

The dashboard SHALL label a day that is partial (the first or last day of collection) or affected by a collector gap, rather than presenting it as a complete day. Where a field is known for only part of the traffic, the view SHALL state the known share.

#### Scenario: A partial day is marked
- **WHEN** the first or last collection day, or a day with a collector gap, is selected
- **THEN** the dashboard indicates that the day is partial or has missing hours
