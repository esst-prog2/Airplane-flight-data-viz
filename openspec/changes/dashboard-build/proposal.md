# Proposal

## Why

The mart now holds the whole collected history, but nothing surfaces it: the project's goal and its class demo both need a visual dashboard over the warehouse. Two audiences need it in two forms — a live dashboard for the presentation while collection is still running, and a permanent, public, no-login version anyone visiting the repository can open after collection ends.

## What Changes

- A new **read-only HTTP API** over the mart (FastAPI, on a dedicated `flights_ro` Postgres role), serving per-day aggregates the dashboard needs. The dashboard can also read the database directly as a fallback.
- A new **Streamlit dashboard** (pure Python; map via `pydeck`) with five views and a **date picker**: pick a day and every view updates for that day.
  1. Map of traffic density (positions hexbin-aggregated)
  2. Daily traffic curve (distinct-aircraft presence per local hour)
  3. Data-quality / coverage (collector gaps, from `fact_hourly_coverage`)
  4. Aircraft **type + country** breakdown
  5. A KPI header band (totals: positions, transits, distinct aircraft, days, catalogue coverage)
- **Two deployment forms** from one codebase, differing only in data source:
  - **Live [A]** on the VPS, reading the read-only API (direct-DB fallback), reflecting current data.
  - **Offline [B]** on Streamlit Community Cloud (free, public, no login), reading a **frozen snapshot** built from the final dump — a presentation backup and a permanent portfolio artifact.
- A **data-source abstraction** hiding the three backends (API / direct DB / frozen snapshot) behind one interface.
- **Non-goals:** operator breakdown (operator is known for only ~1/3 of traffic), transit statistics, and any ML/prediction (the README Vision explicitly excludes ML). The frozen collector (`ingest.py` / `run_loop.py`) and the mart schema are untouched; the mart already has every column the views need.

## Capabilities

### New Capabilities
- `mart-read-api`: a read-only HTTP API over the mart that returns per-day aggregates (map bins, daily curve, coverage, type/country breakdown, KPIs) and never writes, backed by a read-only database role.
- `dashboard-views`: the five dashboard views and the date-picker interaction, including the honesty rules for partial data (e.g. collector-gap days) and the known operator-coverage caveat.
- `dashboard-distribution`: the two forms of the dashboard (live on the VPS; permanent public offline from a frozen snapshot) and the data-source abstraction, with read-only access everywhere and no personal data (`owner`) ever displayed.

### Modified Capabilities
<!-- None. The mart specs and staging-ingestion are unchanged; this change only reads the mart. -->

## Impact

- **New code (Python):** a `dashboard/` Streamlit app (`pydeck`, a charting lib, a date picker) and an `api/` FastAPI service; a data-source abstraction; a script that builds the frozen snapshot from the final dump.
- **Database:** a new read-only role (`flights_ro`, `CONNECT`/`USAGE`/`SELECT` only) — the least-privilege improvement already noted in the README.
- **Infrastructure:** a new container (dashboard + API) in `docker compose` for the live form on the VPS; a Streamlit Community Cloud deployment for the offline form; possibly a reverse proxy / TLS for the live form (first-time technique).
- **Dependencies:** `streamlit`, `fastapi`, `uvicorn`, `pydeck`, a charting library, and a snapshot format library (`duckdb`/`sqlite`) added to the dev/runtime requirements.
- **Untouched:** the collector (`ingest.py`, `run_loop.py`), the mart schema and loads, and the hourly build chain.
