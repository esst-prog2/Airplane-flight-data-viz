"""`flights` — one command-line entry point for the pipeline.

Subcommands:
  flights ingest --once   land one raw poll, run the staging ingest, report landed/
                          accepted/rejected (implemented in a later chunk)
  flights build           run the staging + mart fact loads, print a summary
                          (implemented in a later chunk)
  flights run             start the continuous collector (implemented in a later chunk)

`ingest.py` and `run_loop.py` are frozen: this package imports or subprocesses them,
never modifies them. They live at the repo root, not inside this package, and an
installed console script does not put the repo root on sys.path -- so we add it below,
the same approach dashboard/app.py uses.
"""

import argparse
import sys
from pathlib import Path

# Make the frozen top-level modules (ingest.py, run_loop.py) importable when `flights`
# runs as an installed console script from any directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def ingest_once(conn, land):
    """Run one ingest cycle on `conn` and summarise it.

    `land(conn)` writes the raw rows for this poll (in production the frozen
    collector fetches from the live API and stores them; in tests it writes
    invented rows). We measure how many raw rows it landed, then run the staging
    ingest over the pending raw data and read back the accepted/rejected counts
    and the rejects for this run broken down by reason. Any exception from
    `land` (e.g. an API failure) propagates -- no success is reported.
    """
    before = conn.execute(
        "SELECT COALESCE(max(id), 0) FROM raw.state_snapshot"
    ).fetchone()[0]

    land(conn)

    landed = conn.execute(
        "SELECT count(*) FROM raw.state_snapshot WHERE id > %s", (before,)
    ).fetchone()[0]

    accepted, rejected, wm_from, wm_to = conn.execute(
        "SELECT accepted, rejected, watermark_from, watermark_to"
        " FROM staging.ingest_snapshots()"
    ).fetchone()

    by_reason = conn.execute(
        "SELECT reason, count(*) FROM staging.rejects"
        " WHERE source_raw_id > %s AND source_raw_id <= %s"
        " GROUP BY reason ORDER BY count(*) DESC, reason",
        (wm_from, wm_to),
    ).fetchall()

    return {
        "landed": landed,
        "accepted": accepted,
        "rejected": rejected,
        "by_reason": by_reason,
    }


def _print_ingest_summary(summary):
    print(f"landed (raw):  {summary['landed']}")
    print(f"accepted:      {summary['accepted']}")
    print(f"rejected:      {summary['rejected']}")
    if summary["rejected"]:
        print("rejected by reason:")
        for reason, count in summary["by_reason"]:
            print(f"  {reason}: {count}")


def cmd_ingest(args):
    """Land one poll via the frozen collector, run staging, report the result."""
    if not args.once:
        print(
            "flights ingest runs a single poll; pass --once "
            "(use 'flights run' for continuous collection).",
            file=sys.stderr,
        )
        return 2

    import os

    import psycopg

    import ingest  # frozen collector, importable via the repo-root path insert above

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    def land(_conn):
        # The collector opens its own connection and fetches from the live API;
        # it prints its own landed-rows line and exits non-zero on an API error.
        ingest.main()

    with psycopg.connect(dsn, autocommit=True) as conn:
        summary = ingest_once(conn, land)
    _print_ingest_summary(summary)
    return 0


def _run_step(conn, label, sql, fetch=lambda row: row[0]):
    """Run one build step; on failure raise an error that names the step."""
    try:
        return fetch(conn.execute(sql).fetchone())
    except Exception as exc:  # noqa: BLE001 - re-raised with the step label
        raise RuntimeError(f"build step '{label}' failed: {exc}") from exc


def run_build(conn, with_dims=False):
    """Build the warehouse on `conn`; return (steps, summary).

    Runs the same chain as deploy/mart_build.sh -- staging ingest then the three
    mart fact loads, in dependency order. With `with_dims` it loads the four mart
    dimensions first (for a build against an empty warehouse). Each load is
    incremental and idempotent. Stops at the first failing step (the error, which
    names that step, propagates). `steps` is a list of (label, count); `summary`
    reports the last 24 h of data (relative to the most recent observation, so it
    matches "the last 24 hours" on a live database).
    """
    steps = []

    if with_dims:
        steps.append(("dim_date", _run_step(conn, "dim_date", "SELECT mart.load_dim_date()")))
        steps.append(("dim_time_of_day",
                      _run_step(conn, "dim_time_of_day", "SELECT mart.load_dim_time_of_day()")))
        steps.append(("dim_region",
                      _run_step(conn, "dim_region", "SELECT mart.load_dim_region()")))
        steps.append(("dim_aircraft",
                      _run_step(conn, "dim_aircraft",
                                "SELECT inserted, updated FROM mart.load_dim_aircraft()",
                                fetch=lambda row: row[0] + row[1])))

    steps.append(("staging",
                  _run_step(conn, "staging",
                            "SELECT accepted FROM staging.ingest_snapshots()")))
    steps.append(("fact_position_snapshot",
                  _run_step(conn, "fact_position_snapshot",
                            "SELECT mart.load_fact_position_snapshot()")))
    steps.append(("fact_flight_transit",
                  _run_step(conn, "fact_flight_transit",
                            "SELECT mart.load_fact_flight_transit()")))
    steps.append(("fact_hourly_coverage",
                  _run_step(conn, "fact_hourly_coverage",
                            "SELECT mart.load_fact_hourly_coverage()")))

    segments, known_pct = conn.execute(
        """
        WITH recent AS (
            SELECT aircraft_sk FROM mart.fact_flight_transit
            WHERE last_seen_at > (SELECT max(last_seen_at) FROM mart.fact_flight_transit)
                                 - interval '24 hours'
        )
        SELECT count(*),
               round(100.0 * count(*) FILTER (WHERE a.type_designator <> 'Unknown')
                     / NULLIF(count(*), 0), 1)
        FROM recent r JOIN mart.dim_aircraft a USING (aircraft_sk)
        """
    ).fetchone()

    return steps, {"segments": segments, "known_type_pct": known_pct if known_pct is not None else 0.0}


def _print_build_summary(steps, summary):
    width = max(len(label) for label, _ in steps) + 1
    for label, count in steps:
        print(f"{label + ':':<{width}} {count}")
    print()
    print(
        f"last 24h of data: {summary['segments']} flight segments, "
        f"{summary['known_type_pct']}% matched to a known aircraft type"
    )


def cmd_build(args):
    """Run the staging + mart fact loads over DATABASE_URL and print a summary."""
    import os

    import psycopg

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    with psycopg.connect(dsn, autocommit=True) as conn:
        steps, summary = run_build(conn, with_dims=args.with_dims)
    _print_build_summary(steps, summary)
    return 0


def run_collector(runner=None):
    """Launch the continuous collector (run_loop.py) as a subprocess.

    run_loop.py runs its polling loop at import time, so it cannot be imported --
    we start it as a child process with the current interpreter, inheriting stdio
    so its prints and Ctrl-C behave as if run directly. A Ctrl-C/interrupt stops
    collection and returns control (exit 0). `runner` is the function used to run
    the child (default subprocess.run), injected for testing.
    """
    if runner is None:
        import subprocess

        runner = subprocess.run

    script = REPO_ROOT / "run_loop.py"
    if not script.exists():
        print(f"run_loop.py not found at {script}", file=sys.stderr)
        return 2

    try:
        completed = runner([sys.executable, str(script)])
    except KeyboardInterrupt:
        return 0
    return getattr(completed, "returncode", 0)


def cmd_run(args):
    """Start the continuous collector (polls until interrupted)."""
    return run_collector()


def build_parser():
    """Build the argparse parser with the ingest/build/run subcommands."""
    parser = argparse.ArgumentParser(
        prog="flights",
        description="Run the Airplane-flight-data-viz pipeline from one entry point.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="{ingest,build,run}")

    p_ingest = subparsers.add_parser(
        "ingest", help="Fetch and land air-traffic snapshots over the bounding box."
    )
    p_ingest.add_argument(
        "--once",
        action="store_true",
        help="Land a single poll, then run the staging ingest and report the result.",
    )
    p_ingest.set_defaults(func=cmd_ingest)

    p_build = subparsers.add_parser(
        "build", help="Build the star schema (staging ingest + mart fact loads)."
    )
    p_build.add_argument(
        "--with-dims",
        action="store_true",
        help="Load the four mart dimensions first (for a build from an empty warehouse).",
    )
    p_build.set_defaults(func=cmd_build)

    p_run = subparsers.add_parser(
        "run", help="Start the continuous collector (polls until interrupted)."
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv=None):
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
