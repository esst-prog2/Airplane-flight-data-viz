# Tasks

## 1. Read-only access and the data-source interface

- [x] 1.1 Confirm the design decisions needed before building chunk 1 — D2 map binning decided = **H3 hexagons, resolution 5** (PLANNING_LOG 2026-10-29); D5 (Plotly) and D7 (Caddy + HTTPS, free domain) already decided; D3 snapshot format (SQLite) is confirmed at chunk 4 where it is first used; any change logged in `PLANNING_LOG.md`
- [x] 1.2 Define the `DataSource` protocol (`date_range`, `kpis`, `day_map`, `day_curve`, `day_coverage`, `day_breakdown`) in `dashboard/datasource.py`; verified it imports and the `runtime_checkable` Protocol type-checks
- [x] 1.3 Write the per-day aggregation SQL over the mart in `dashboard/queries.py` (H3-binned map positions, distinct-aircraft hourly curve in local time, hourly coverage, type+country breakdown, dataset KPIs); verified each returns the expected shape against the dev DB for 2026-10-21
- [x] 1.4 Implement `DbSource` (direct psycopg, read-only; H3 binning via the `h3` library) over those queries; verified it returns aggregates for a day with data (date_range, KPIs, 24-row curve, coverage, type/country breakdown, 1830 H3 map cells)
- [x] 1.5 Add `flights_ro` role DDL (`CONNECT`/`USAGE`/`SELECT` only) as `sql/roles/flights_ro.sql`; verified on the dev DB via `SET ROLE` that it can `SELECT` and that an `INSERT` is refused (permission denied)

## 2. Read-only API

- [ ] 2.1 Implement the FastAPI service (`GET /meta`, `/day/{date}/map`, `/day/{date}/curve`, `/day/{date}/coverage`, `/day/{date}/breakdown`) over `DbSource` on `flights_ro`; verify each endpoint returns JSON aggregates for a known day via the test client
- [ ] 2.2 Implement `ApiSource` (HTTP client) against the API; verify it yields the same aggregates as `DbSource` for the same day
- [ ] 2.3 Add API tests: endpoint shapes, an empty day returns zeroed aggregates (not an error), responses carry no raw position rows and no `owner` field; verify green and red-checked

## 3. Streamlit dashboard and the five views

- [ ] 3.1 Scaffold the Streamlit app and the date picker (defaults to the latest local day with data, bounded to the available range); verify picking a day drives the value the views read
- [ ] 3.2 Map view: `pydeck` hex cells for the selected day; verify a busy day renders denser cells when run locally
- [ ] 3.3 Daily curve: Altair chart of distinct-aircraft presence over the 24 local hours; verify it renders 24 hourly points for the selected day
- [ ] 3.4 Coverage view: mark hours that were not fully covered for the selected day; verify a known gap day shows the missing hours flagged
- [ ] 3.5 Type + country breakdown (no operator, no `owner`); verify it lists counts by type and country only
- [ ] 3.6 KPI header band (dataset totals: positions, transits, distinct aircraft, days, catalogue coverage); verify the figures match a direct SQL count
- [ ] 3.7 Partial/gap-day labelling and the operator-coverage caveat text; verify a partial first/last day is marked as partial

## 4. Offline form (frozen snapshot)

- [ ] 4.1 Implement the snapshot-build script: run the aggregation queries over the data and write per-day aggregate tables into a SQLite file (no raw positions, no `owner`); verify the file opens and a spot-check day matches the live query
- [ ] 4.2 Implement `SnapshotSource` reading the SQLite file; verify the dashboard renders identical views from the snapshot and from `DbSource` for the same day
- [ ] 4.3 Prepare the Streamlit Community Cloud entrypoint (reads the bundled snapshot, pinned requirements); verify the app runs against the snapshot with no database reachable

## 5. Deploy, documentation, and the final publish

- [ ] 5.1 Add the dashboard+API container to `docker compose`; verify it builds and serves the views locally
- [ ] 5.2 Deploy the live form on the VPS behind the chosen exposure (Caddy or `IP:port`) reading the API with DB fallback (user runs the VPS writes); verify the live URL shows the most recent day
- [ ] 5.3 After collection ends (late Nov 2026): rebuild the frozen snapshot from the final data and publish the offline form to Streamlit Community Cloud; verify the public URL opens with no login and shows the final data
- [ ] 5.4 Update `README.md`: move the dashboard out of "Not yet built" into the built section and add both URLs; verify the Status section matches what is deployed
