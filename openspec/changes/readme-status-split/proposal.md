# Proposal

## Why

The README currently describes the project's target shape ("the demo", "the size", "how we would know it works") in the present tense, as if it were already built. In reality, only the collector (`ingest.py` + `run_loop.py`), the raw landing table, and the Docker/Postgres scaffolding exist today; staging, the star schema, the data-quality table, the dashboard, and the `flights` CLI referenced in the demo do not. Anyone opening the README cannot tell what is running versus what is planned, and the documented demo command (`docker compose up -d` starting three containers, then `flights ingest --once`) does not work against the current code. Splitting the README into a status-labeled structure fixes that mismatch without changing any code.

## What Changes

- Restructure `README.md` so it has a clearly separated **current status** section (what is built and runnable today) and a **vision / target** section (the original "first useful version" scope, demo walkthrough, and non-goals), so the two are never read as the same thing.
- Update the Setup section to describe only what actually runs today (Postgres + collector via `docker compose up -d`; no dashboard container, no `flights` CLI) and note that the fuller demo in the vision section is aspirational.
- Add an explicit note that `ingest.py` and `run_loop.py` (the collector) are considered complete and frozen: the collection layer is the project's one irreversible component (every day not collected is a day of history that can never be backfilled), and no proposal in this project may modify those two files.
- No behavior, schema, or code changes — documentation only.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None — this is a documentation-only change with no spec-level behavior change. `skip_specs: true` is set in `.openspec.yaml`.

## Impact

- `README.md` only.
- No effect on `ingest.py`, `run_loop.py`, SQL, Docker, or any runtime behavior.
