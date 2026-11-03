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


def cmd_ingest(args):
    """Land one poll and report what was landed and refused. (Chunk 2.)"""
    raise NotImplementedError("flights ingest is implemented in a later chunk")


def cmd_build(args):
    """Run the staging + mart fact loads and print a summary. (Chunk 3.)"""
    raise NotImplementedError("flights build is implemented in a later chunk")


def cmd_run(args):
    """Start the continuous collector as a subprocess. (Chunk 4.)"""
    raise NotImplementedError("flights run is implemented in a later chunk")


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
