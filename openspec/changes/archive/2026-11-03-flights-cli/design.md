# Design

## Context

See proposal.md — Why. The pipeline already works through `ingest.py`, `run_loop.py`,
the staging/mart SQL functions, and the `deploy/*.sh` scripts. Two hard constraints shape
this change: `ingest.py` and `run_loop.py` are **frozen** (no edits), and the VPS cron
that runs the `deploy/*.sh` scripts must keep working untouched. The CLI is a thin wrapper
over what exists, added for humans and the demo.

## Goals / Non-Goals

**Goals**
- One installed `flights` command with `ingest`, `build`, `run` subcommands.
- Make the README "The demo" commands real and runnable as written.
- Zero new runtime dependencies.

**Non-Goals**
- Not the production scheduler: cron keeps calling the shell scripts; the CLI does not
  replace or modify them.
- No new pipeline behavior — only orchestration of existing functions/scripts.
- No CLI flags beyond those the three subcommands need (`--once`, `--with-dims`).

## Decisions

### Package layout and entry point
A new `flights/` package (`flights/__init__.py`, `flights/cli.py` with `main()`), and a
minimal `pyproject.toml` declaring `[project.scripts] flights = "flights.cli:main"`.
Installed once with `pip install -e .`, so `flights` is a bare command.
- *Why over `python -m flights`*: the README/demo promise the bare `flights` command; a
  console entry point delivers exactly that and is the conventional packaging approach.

### Reaching the frozen top-level modules from the installed command
`ingest.py` and `run_loop.py` live at the repo root, not inside the `flights/` package.
An installed console script does not run with the repo root on `sys.path`, so
`flights/cli.py` must make the root importable before `import ingest`. It resolves the
repo root from its own file location (`Path(__file__).resolve().parent.parent`) and inserts
it on `sys.path` — the same approach `dashboard/app.py` already uses. The `pyproject.toml`
packages only the `flights` package; the frozen root modules are reached at runtime via the
path insert, not by packaging them.
- *Alternative considered*: declare `ingest`/`run_loop` as top-level `py-modules` in
  `pyproject.toml`. Rejected: it pulls the frozen files into the install surface and is
  more fragile under editable installs than the explicit, already-proven path insert.

### `ingest --once`: import the collector, then stage
`flights/cli.py` does `import ingest; ingest.main()` (one raw poll — `main()` is clean and
side-effect-free at import), then runs `staging.ingest_snapshots()` over `DATABASE_URL`.
It reports the raw rows landed and the accepted/rejected counts, with rejects grouped by
reason from `staging.rejects`.
- *Why call `ingest.main()` directly*: it prints its own landed-rows line and has a clean
  `main()`; importing avoids a subprocess.
- *Note*: `staging.ingest_snapshots()` is watermark-based — it processes all pending raw
  rows, not strictly this poll's. On a caught-up DB that is effectively this poll; this is
  accepted behavior, not a bug.

### `run`: subprocess, not import
`run_loop.py` runs its `while True` loop at module import, so it cannot be imported without
blocking. `flights run` launches it as a subprocess: `subprocess.run([sys.executable,
"<root>/run_loop.py"])`, inheriting stdio so its prints and Ctrl-C behave normally.

### `build`: call the mart functions over `DATABASE_URL`
`flights build` connects with `psycopg` to `DATABASE_URL` and issues `SELECT` on the same
functions the cron chain uses, in order: `staging.ingest_snapshots()`,
`mart.load_fact_position_snapshot()`, `mart.load_fact_flight_transit()`,
`mart.load_fact_hourly_coverage()`. `--with-dims` first runs the four
`mart.load_dim_*()` functions. It prints each step's returned count, then a summary query:
flight segments in the last 24 h and the share joined to a non-unknown `dim_aircraft`.
- *Why psycopg over `DATABASE_URL`, not `docker compose exec psql`*: the shell scripts run
  on the VPS where Postgres is a compose service; the CLI runs wherever a developer points
  `DATABASE_URL` (local dev DB bound to `127.0.0.1`, or the VPS). psycopg is already a
  dependency and keeps the CLI host-agnostic. The shell scripts remain the production path.

### Library: argparse
Standard-library `argparse` with subparsers. No new dependency; sufficient for three
subcommands and two flags.

## Risks / Trade-offs

- **Editable-install import of root modules is environment-sensitive** → mitigated by the
  explicit `sys.path` insert from `__file__` (proven in `dashboard/app.py`), covered by a test.
- **`build` summary query drift** (column/function names) → the summary is a read-only
  `SELECT`; a test asserts it runs and returns the expected shape against a seeded DB.
- **Two ways to run the same steps** (CLI vs cron scripts) could diverge → the CLI calls the
  very same SQL functions as `mart_build.sh`; it adds no load logic of its own, so they cannot
  diverge in behavior, only in invocation.
- **`run` as a subprocess** means signals pass through the child → inheriting stdio and
  letting the child handle Ctrl-C keeps behavior identical to `python run_loop.py`.

## Migration Plan

Additive only. New `flights/` package and `pyproject.toml`; no existing file changes except
README usage docs. Deploy is a one-time `pip install -e .` where the CLI is wanted (dev
machine, demo). Rollback: uninstall / ignore the command — nothing else depends on it, and
the cron/shell path is unaffected.

## Open Questions

None that affect the specs, approach, or task breakdown.
