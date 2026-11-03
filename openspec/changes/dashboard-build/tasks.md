# Tasks

## 1. Read-only access and the data-source interface

- [x] 1.1 Confirm the design decisions needed before building chunk 1 — D2 map binning decided = **H3 hexagons, resolution 5** (PLANNING_LOG 2026-10-29); D5 (Plotly) and D7 (Caddy + HTTPS, free domain) already decided; D3 snapshot format (SQLite) is confirmed at chunk 4 where it is first used; any change logged in `PLANNING_LOG.md`
- [x] 1.2 Define the `DataSource` protocol (`date_range`, `kpis`, `day_map`, `day_curve`, `day_coverage`, `day_breakdown`) in `dashboard/datasource.py`; verified it imports and the `runtime_checkable` Protocol type-checks
- [x] 1.3 Write the per-day aggregation SQL over the mart in `dashboard/queries.py` (H3-binned map positions, distinct-aircraft hourly curve in local time, hourly coverage, type+country breakdown, dataset KPIs); verified each returns the expected shape against the dev DB for 2026-10-21
- [x] 1.4 Implement `DbSource` (direct psycopg, read-only; H3 binning via the `h3` library) over those queries; verified it returns aggregates for a day with data (date_range, KPIs, 24-row curve, coverage, type/country breakdown, 1830 H3 map cells)
- [x] 1.5 Add `flights_ro` role DDL (`CONNECT`/`USAGE`/`SELECT` only) as `sql/roles/flights_ro.sql`; verified on the dev DB via `SET ROLE` that it can `SELECT` and that an `INSERT` is refused (permission denied)

## 2. Read-only API

- [x] 2.1 Implement the FastAPI service (`GET /meta`, `/day/{date}/map`, `/day/{date}/curve`, `/day/{date}/coverage`, `/day/{date}/breakdown`) in `dashboard/api.py` over `DbSource` (DSN from `DASHBOARD_DSN`/`flights_ro`, falling back to `DATABASE_URL`); verified each endpoint returns JSON aggregates via the TestClient
- [x] 2.2 Implement `ApiSource` (HTTP client, pluggable `client` for testing) in `dashboard/datasource.py`; verified it yields the same aggregates as `DbSource` for the same day
- [x] 2.3 Add API tests in `tests/test_dashboard_api.py` on a throwaway DB: endpoint shapes, an empty day returns zeroed aggregates (not an error), the map returns aggregated cells (count 2 for two positions) not raw rows, and no `owner` field anywhere; 6 tests green, full suite 33 passed / 1 skipped

## 3. Streamlit dashboard and the five views

- [x] 3.1 Scaffold the Streamlit app (`dashboard/app.py`) and the date picker (defaults to the latest local day, bounded to the available range; source via `DASHBOARD_API_URL` else `DATABASE_URL`); verified with `streamlit.testing` AppTest that the script runs, the picker exists, and views read the chosen day
- [x] 3.2 Map view: `pydeck` **H3HexagonLayer** for the selected day (`views.map_deck`, count → elevation + colour ramp); verified via AppTest it renders without error and a unit test that one layer covers all cells
- [x] 3.3 Daily curve: **Plotly** (D5, not Altair) bar chart of distinct-aircraft presence over the 24 local hours, peak hours highlighted; verified a 24-point figure in `tests/test_dashboard_views.py`
- [x] 3.4 Coverage view: Plotly bars coloured green/red by `is_fully_covered` for the selected day; verified a gap hour is coloured red in the view test
- [x] 3.5 Type + country breakdown (`views.breakdown_figures`, no operator, no `owner`); verified two figures build and the API/data layer already exclude owner
- [x] 3.6 KPI header band (positions, transits, distinct aircraft, days, catalogue coverage); verified via AppTest the metrics populate from the dev DB (1,062,851 positions, 87% coverage, …) and formatting in the view test
- [x] 3.7 Partial/gap-day labelling (`views.partial_day_note`) and the operator-coverage caveat caption; verified the note appears for unobserved/not-fully-covered hours and is absent for a clean day

## 4. Offline form (frozen snapshot)

- [x] 4.1 Implement the snapshot-build script `dashboard/build_snapshot.py` (D3 = SQLite): reads the mart via `DbSource` and writes per-day aggregate tables (map/curve/coverage/breakdown + a meta row) into one SQLite file, no raw positions and no `owner`; verified a test build opens and reads back identically to the live query, and a dev build is 5.08 MB for 48 days
- [x] 4.2 Implement `SnapshotSource` (stdlib `sqlite3`) reading the file; verified it reads back identically to `DbSource` for the same day (date range, default day, KPIs, curve, coverage, breakdown, map) in `tests/test_dashboard_snapshot.py`
- [x] 4.3 Wire the offline entrypoint: `app.make_source()` selects `SnapshotSource` when `DASHBOARD_SNAPSHOT` is set (API → snapshot → DB); verified via AppTest that the app runs end to end from the snapshot alone with `DATABASE_URL` unset (KPIs and all four views render). Streamlit Cloud deploy (pinned requirements, bundled file) is wired in chunk 5

## 5. Deploy, documentation, and the final publish

- [x] 5.1 Add the dashboard+API services to `docker compose` (new `Dockerfile.dashboard`; `api` = uvicorn on the `flights_ro` role, internal only; `dashboard` = streamlit, API-backed with a direct-DB `FallbackSource`, published on `127.0.0.1:8501`); verified `docker compose config` is valid, the image builds, and the container serves (Streamlit health = ok). Fallback covered by `tests/test_dashboard_fallback.py`
- [ ] 5.2 Deploy the live form on the VPS behind the chosen exposure (Caddy or `IP:port`) reading the API with DB fallback (user runs the VPS writes); verify the live URL shows the most recent day
- [ ] 5.3 After collection ends (late Nov 2026): rebuild the frozen snapshot from the final data and publish the offline form to Streamlit Community Cloud; verify the public URL opens with no login and shows the final data
- [ ] 5.4 Update `README.md`: move the dashboard out of "Not yet built" into the built section and add both URLs; verify the Status section matches what is deployed
