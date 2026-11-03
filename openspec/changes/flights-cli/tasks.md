# Tasks

## 1. Package and entry point

- [x] 1.1 Create the `flights/` package (`flights/__init__.py`, `flights/cli.py` with a
  `main()` that builds an `argparse` parser with `ingest`/`build`/`run` subparsers) and a
  minimal `pyproject.toml` declaring `[project.scripts] flights = "flights.cli:main"`;
  verify `pip install -e .` succeeds and `flights --help` lists the three subcommands and
  exits zero, and an unknown subcommand exits non-zero.
- [x] 1.2 In `flights/cli.py`, resolve the repo root from `__file__` and insert it on
  `sys.path` before importing the frozen top-level modules (same pattern as
  `dashboard/app.py`); verify `import ingest` works from the installed `flights` command
  (covered by the ingest test in chunk 2).

## 2. `flights ingest --once`

- [x] 2.1 Implement the `ingest` subcommand: call `ingest.main()` to land one raw poll, then
  run `staging.ingest_snapshots()` over `DATABASE_URL`, and print raw rows landed plus the
  accepted and rejected counts with rejects grouped by reason (from `staging.rejects`);
  a fetch or DB failure exits non-zero without reporting success.
- [x] 2.2 Add `tests/test_cli.py` coverage for `ingest`: on a throwaway/seeded DB (reuse the
  staging test helpers), verify the command runs the staging ingest and prints the landed /
  accepted / rejected-by-reason summary, and that a simulated fetch failure exits non-zero;
  verify the test passes.

## 3. `flights build`

- [x] 3.1 Implement the `build` subcommand: over `DATABASE_URL` run
  `staging.ingest_snapshots()` then `mart.load_fact_position_snapshot()`,
  `mart.load_fact_flight_transit()`, `mart.load_fact_hourly_coverage()` in order, printing
  each step's returned count; stop and exit non-zero on the first failing step. Add
  `--with-dims` to first run the four `mart.load_dim_*()` functions.
- [x] 3.2 Add the build summary: after the loads, run a read-only query for flight segments
  in the last 24 h and the share joined to a non-unknown `dim_aircraft`, and print it;
  verify in `tests/test_cli.py` against a seeded mart that `build` runs the steps in order,
  prints per-step counts and the summary line, and that `--with-dims` loads dimensions first.

## 4. `flights run`

- [x] 4.1 Implement the `run` subcommand to launch `run_loop.py` as a subprocess
  (`subprocess.run([sys.executable, "<root>/run_loop.py"])`, inheriting stdio); verify with
  a test that patches `subprocess.run` that `flights run` invokes `run_loop.py` with the
  current interpreter (not imported), and that Ctrl-C/interrupt returns control.

## 5. Documentation

- [x] 5.1 Update `README.md`: move the `flights` CLI from "Not yet built" into the built
  section, document the one-time `pip install -e .` and the three commands, and confirm the
  "The demo" commands now match reality; verify the README reflects what is built and append
  the outcome to `PLANNING_LOG.md`.
- [x] 5.2 Run the full test suite (`pytest`) and confirm it is green (including the new CLI
  tests) with no new runtime dependency added to `requirements.txt`.
