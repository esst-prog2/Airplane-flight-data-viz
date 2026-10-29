# Design

## Context

See proposal.md — Why. The mart is built, deployed and running hourly on the VPS; it already carries every column the views need (positions with lat/lon, local/UTC date and time-of-day keys, `aircraft_sk` → type/country, `fact_hourly_coverage`). The collector and the mart schema are frozen for this change — the dashboard only reads. Two forms are required: a live form on the VPS while collection runs, and a permanent public form from a frozen snapshot after collection ends (see [[dashboard-distribution]]).

Constraints that shape the approach: pure Python (no hand-written HTML/CSS); read-only database access; the raw position volume (~6.96M rows, ~170k/day) must never reach the browser; the offline form must run with no live database and no login on a free host.

## Goals / Non-Goals

**Goals:**
- One Streamlit codebase that renders the five views (see [[dashboard-views]]) against any of three backends behind one interface.
- A read-only HTTP API (see [[mart-read-api]]) that returns per-day aggregates only.
- A frozen snapshot of per-day aggregates small enough to host free and publicly.

**Non-Goals (design-level):**
- No raw-position transport to the client; all map data is pre-binned.
- No write path of any kind; no auth/accounts (the offline form is public read-only).
- No operator view, no transit stats, no ML (proposal non-goals).
- Not solving multi-region or multi-user concurrency — single region, read-only viewers.

## Decisions

### D1 — Data-source abstraction: one interface, three backends
A `DataSource` protocol exposes exactly what the views need: `date_range()`, `kpis()`, `day_map(date)`, `day_curve(date)`, `day_coverage(date)`, `day_breakdown(date)`. Three implementations: `ApiSource` (HTTP → FastAPI), `DbSource` (direct psycopg → Postgres, the live fallback), `SnapshotSource` (reads the frozen file). The Streamlit app depends only on the protocol, so the same views serve both forms. *Alternative rejected:* bespoke code per form — duplicates view logic.

### D2 — Map binning: pre-aggregated hex cells `[CONFIRM]`
The map shows pre-aggregated hexagon cells (cell centre + count), rendered by `pydeck` (`HexagonLayer`/`ColumnLayer`). Binning is done in SQL/at snapshot-build time, never in the browser. **Proposed default:** H3 at **resolution 5** (~8 km cells over the ~600 km box) via the `h3` library. *Alternative:* a dependency-free lat/lon grid (round to 0.1°) if we prefer no new library. To confirm before apply.

### D3 — Snapshot format: a bundled SQLite file `[CONFIRM]`
The frozen snapshot is a single **SQLite** file holding per-day aggregate tables (map bins, hourly curve, coverage, type/country, plus one KPI row), committed with the repo and read by `SnapshotSource` via the stdlib `sqlite3`. It holds no raw positions and no `owner`, so it stays a few MB. *Alternative:* DuckDB/Parquet (stronger analytics, heavier dependency) — overkill for pre-aggregated data. To confirm before apply.

### D4 — API shape: a few read-only per-day endpoints
`GET /meta` (date range + dataset KPIs), `GET /day/{date}/map`, `/day/{date}/curve`, `/day/{date}/coverage`, `/day/{date}/breakdown`. FastAPI + `uvicorn`, connecting as `flights_ro`. Responses are aggregates (JSON), never raw rows. *Alternative rejected:* PostgREST (auto REST) — less control and still needs the same role; a small hand-written API is the learning goal and keeps payloads shaped for the views.

### D5 — Charting: Altair for the 2-D charts `[CONFIRM]`
Curve, coverage and breakdown use **Altair** (declarative, clean defaults, native Streamlit support); the map uses `pydeck`. *Alternative:* Plotly (more interactive, heavier). To confirm before apply.

### D6 — Timezone: everything the viewer sees is `Europe/Budapest` local
Day selection, the daily curve's hours, and coverage are all in local time (UTC is internal only), matching how `is_peak_traffic` and the measured curve were derived. The default day is the most recent local day with data.

### D7 — Live exposure on the VPS `[CONFIRM]`
The live form runs as a new container (Streamlit + the API) in `docker compose`. **Proposed default:** put it behind **Caddy** for automatic HTTPS if a domain is available; otherwise reach it by `IP:port` for the presentation. To confirm before apply (depends on whether a domain exists).

## Risks / Trade-offs

- **Streamlit Community Cloud dependency for the offline form** → it is free and public but third-party; mitigate by keeping the snapshot + app fully self-contained (any Python host, or even local `streamlit run`, can serve it), so the public URL can move.
- **Per-request aggregation cost on the live API** (~170k rows/day grouped per call) → the existing time/position indexes keep it fast; cache per-day responses in the API if needed.
- **Snapshot staleness by design** → the offline form is explicitly a frozen final-data artifact, not live; this is intended.
- **Map over-plotting / browser load** → mitigated by pre-binning (D2); the browser only ever receives cells.
- **A new library (`h3`) and TLS/reverse proxy are firsts** → both are isolated (binning is one function; Caddy is one config) and have dependency-free / IP-only fallbacks.

## Migration Plan

1. Create the `flights_ro` read-only role on the VPS (user runs the write; `CONNECT`/`USAGE`/`SELECT` only).
2. Build the API and dashboard locally against the dev DB; verify the three data sources render identical views.
3. Add the dashboard+API container to `docker compose`; deploy the live form on the VPS (behind Caddy or on `IP:port` per D7).
4. At collection end (late Nov 2026): build the frozen SQLite snapshot from the final data, deploy the offline form to Streamlit Community Cloud, and link it from the README.

**Rollback:** the change is read-only and additive — removing the container and the `flights_ro` role reverts it with zero effect on the collector, the raw data or the mart.

## Open Questions

- Exact H3 resolution (or grid size) is a visual-tuning detail that can be adjusted after seeing the first map without changing the specs or the task breakdown.
- Whether to add a weekday-vs-weekend or multi-day comparison later — a possible future enhancement, out of this change.
