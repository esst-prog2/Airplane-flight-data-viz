"""
Regression guard for the transit segmentation on real data.

Unlike the other mart tests (which run on invented data in a throwaway
database via conftest.py), this one runs against the real warehouse
(DATABASE_URL) and checks that the 600 s segmentation produces a
plausible number of transits over a fixed, fully-covered 2-day window.

The window 2026-10-20..2026-10-22 UTC is entirely in the past, every one
of its 48 hours is fully covered, and the mart loads are idempotent, so
the count is stable: 17,242 transits on the VPS when this test was
written (cf. 17,272 logged on 2026-10-21). The assertion is a +/-20%
band, not an exact match: its job is to catch a gross regression in the
stitching logic (a doubling or halving of the count), not to pin the
exact number. A deliberate change to the 600 s threshold is expected to
fail this test -- that is the point.

The guard is the POSITION count in the window, not the transit count: a
segmentation regression changes how positions are grouped into transits
but not how many positions land, so positions measure whether the
connected database actually holds the full dataset. Below ~80% of the
VPS position volume the database is a partial copy (e.g. the local dev
database, which holds a fraction of the VPS data), and the VPS-measured
transit band does not apply, so the test skips rather than fails.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

WINDOW_START = "2026-10-20 00:00:00+00"
WINDOW_END = "2026-10-22 00:00:00+00"

# measured 2026-10-28 on the VPS over this fixed, fully-covered window
EXPECTED_TRANSITS = 17_242
LOW = 13_800    # -20%
HIGH = 20_700   # +20%

EXPECTED_POSITIONS = 307_996
# below ~80% of the real position volume the database is a partial copy
MIN_POSITIONS = 246_000


def test_transit_count_over_a_fixed_window_stays_in_band():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT count(*) FROM mart.fact_position_snapshot
                      WHERE time_position_utc >= %(s)s AND time_position_utc < %(e)s),
                    (SELECT count(*) FROM mart.fact_flight_transit
                      WHERE first_seen_at >= %(s)s AND first_seen_at < %(e)s)
                """,
                {"s": WINDOW_START, "e": WINDOW_END},
            )
            positions, transits = cur.fetchone()

    if positions < MIN_POSITIONS:
        pytest.skip(
            f"only {positions} positions in {WINDOW_START}..{WINDOW_END} "
            f"(< {MIN_POSITIONS}); the connected database is a partial copy, so "
            "the VPS-measured transit band does not apply -- run this against the "
            "VPS warehouse or a full restore of it"
        )

    assert LOW <= transits <= HIGH, (
        f"transit count {transits} is outside the +/-20% band [{LOW}, {HIGH}] "
        f"around the VPS-measured {EXPECTED_TRANSITS} (positions={positions}); "
        "the 600 s segmentation logic may have regressed"
    )
