# PLANNING_LOG

One line per decision: date, what was decided, who decided it (user or agent).

- 2026-09-22 — Install Node.js LTS via winget, since Node was missing entirely — decided by: user
- 2026-09-22 — OpenSpec version 1.13.9 does not exist on npm; install `@fission-ai/openspec@1.13.1` (latest) instead — decided by: user
- 2026-09-22 — `openspec init` tool target: `claude` (Claude Code integration) — decided by: user
- 2026-09-22 — Split README.md into a "Status" section (what runs today) and a "Vision" section (target shape), so the README stops overstating current capability — decided by: user
- 2026-09-22 — `ingest.py` and `run_loop.py` (the collector) must never be modified by any future change — the collector is the project's one irreversible part — decided by: user
- 2026-09-22 — Next build slice after the README split: the staging layer and a rejects table, built in SQL from `raw.state_snapshot` — decided by: user
- 2026-09-22 — Staging transform must be idempotent and repeatable (not a one-off script), for robustness — decided by: user
- 2026-09-22 — No separate checkpoint table; the watermark is derived each run as `MAX(raw_id)` across `staging.state_position` and `staging.rejects` — decided by: user (confirming agent's proposal)
- 2026-09-22 — Four hard reject rules: `missing_icao24`, `missing_position`, `missing_time_position`, `impossible_coordinate` (out of lat/lon range or exactly 0,0) — decided by: user
- 2026-09-22 — Missing/implausible altitude, missing callsign, and stale position are flags kept in staging, not reject reasons — decided by: user (confirming agent's proposal)
- 2026-09-22 — Stale-position threshold: 1800 s (30 min), measured from the project's own collected data (p999 lag ~3138 s) — decided by: user (confirming agent's data-grounded proposal)
- 2026-09-22 — Implausible-altitude threshold: 18,288 m (60,000 ft), measured from the project's own collected data (legit traffic tops out ~14,333 m; one aircraft showed a stuck-sensor value of 27,706 m) — decided by: user (confirming agent's data-grounded proposal)
- 2026-09-22 — `staging.rejects` lives in the `staging` schema, not `raw` — decided by: user
- 2026-09-22 — New capability name for this slice: `staging-ingestion` — decided by: user (confirming agent's proposal)
- 2026-09-22 — Project constraint: this is a university project; data collection runs only until roughly end of November / early December 2026, by which all README "Vision" requirements plus a dashboard must be implemented — decided by: user
- 2026-09-22 — Push destination: `upstream` (`github.com/esst-prog2/Airplane-flight-data-viz`) directly, not just the personal fork — decided by: user
- 2026-09-22 — Also push the same commit to `origin` (personal fork) to keep it in sync — decided by: user
- 2026-09-30 — hw4 spike question: what fraction of the last two weeks did the collector actually cover (≥28 of ~30 polls/hour), and how many aircraft gaps survive once gaps touching any under-covered hour are removed? Answer method: one SQL pass, `sql/spike/collector_coverage.sql` — decided by: user
- 2026-09-30 — hw4 spike result: over the 14 days ending 2026-09-30 08:13 UTC, only 6.82% of hours (23 of 337) had ≥28 distinct polls; of 258,981 consecutive per-icao24 gaps in `staging.state_position` in that window, 178,237 survive after discarding gaps touching any under-covered hour — decided by: agent (measured, per user's spike request)
- 2026-09-30 — Because of the low measured coverage (6.82%), the hourly data-quality/collection-coverage table is now the higher-priority Vision gap over flight-stitching; README Status and the staging-ingestion design.md Risks section updated to record the measured figure — decided by: agent (confirming user's spike-driven priority)
