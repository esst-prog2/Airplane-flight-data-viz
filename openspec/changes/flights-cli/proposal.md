# Proposal

## Why

The project's operations are reached today through scattered entry points —
`python ingest.py`, `python run_loop.py`, and the `deploy/*.sh` shell scripts —
so a newcomer (or the grader at the demo) must know which file does what and in
what order. The README "The demo" section already promises a single `flights`
command (`flights ingest --once`, `flights build`); this change makes that
promise real so the demo can be run exactly as written.

## What Changes

- Add a new `flights` command-line entry point (installed as a console script via
  a minimal `pyproject.toml`), with three subcommands:
  - `flights ingest --once` — lands one raw poll via the frozen collector, then
    runs the staging ingest, and prints what landed and what was refused (by reason).
  - `flights build` — runs the staging ingest and the three mart fact loads (the
    same chain as `deploy/mart_build.sh`), with a `--with-dims` flag to load the
    four dimensions first; prints per-step counts plus a short demo-style summary
    (flight segments in the last 24 h and the share matched to a known aircraft type).
  - `flights run` — starts the continuous collector (`run_loop.py`) as a subprocess.
- Add a new `flights/` Python package (`flights/cli.py` + entry point) and a minimal
  `pyproject.toml` declaring the console script. No new runtime dependencies
  (standard-library `argparse` only; the mart functions are called over the existing
  `psycopg`/`DATABASE_URL`).

Non-goals: this does not change how the system runs in production. The VPS cron keeps
running the `deploy/*.sh` scripts untouched — the CLI is a convenience/demo layer for
humans. The frozen collector is not modified (`ingest.py` is imported; `run_loop.py`
is launched as a subprocess because its loop runs at import time).

## Capabilities

### New Capabilities
- `cli`: a single `flights` command-line interface that wraps the existing collector,
  staging ingest, and mart build behind three subcommands (`ingest`, `build`, `run`),
  so the whole pipeline can be driven from one documented entry point.

### Modified Capabilities
<!-- None. The wrapped behaviors (collector, staging ingest, mart loads) are unchanged;
     the CLI only invokes the existing functions and scripts. -->

## Impact

- **New code:** `flights/` package (`flights/__init__.py`, `flights/cli.py`),
  `pyproject.toml` (console entry point `flights = "flights.cli:main"`), and tests
  (`tests/test_cli.py`).
- **Frozen files:** `ingest.py` and `run_loop.py` are untouched (imported / subprocessed).
- **Deploy:** the `deploy/*.sh` scripts and the VPS cron are untouched; the CLI is an
  additional, optional way to run the same steps locally or in the demo.
- **Dependencies:** no new runtime dependency; installation adds a one-time
  `pip install -e .` step (documented in the README).
- **Docs:** README demo/usage updated to show the real `flights` commands once built.
