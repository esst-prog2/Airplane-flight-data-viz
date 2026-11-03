"""
Data access behind one interface, so the five views serve both forms of the
dashboard unchanged (see the dashboard-distribution spec). Chunk 1 adds the
`DataSource` protocol and `DbSource`, the direct read-only database backend —
the live fallback and what the API wraps. `ApiSource` (live) and `SnapshotSource`
(offline) arrive in later chunks.

Every method returns plain Python values (dicts / lists) so the same results
serialize to JSON for the API and feed the Streamlit views directly.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Protocol, runtime_checkable

from . import queries


def day_sk(day: dt.date) -> int:
    """The mart.dim_date surrogate key for a calendar day (YYYYMMDD)."""
    return day.year * 10000 + day.month * 100 + day.day


def sk_to_date(sk: int | None) -> dt.date | None:
    """Inverse of `day_sk`: a YYYYMMDD surrogate key back to a date."""
    if sk is None:
        return None
    sk = int(sk)
    return dt.date(sk // 10000, (sk // 100) % 100, sk % 100)


@runtime_checkable
class DataSource(Protocol):
    """What every view needs, independent of where the data comes from."""

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        """Earliest and latest local day that has data (None, None if empty)."""

    def default_day(self) -> dt.date | None:
        """The day to open on: the latest fully-covered day, else the latest day."""

    def kpis(self) -> dict[str, Any]:
        """Dataset-wide headline totals for the KPI band."""

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        """H3 cells for the day: {h3, lat, lon, count}."""

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        """24 rows {hour, aircraft}: distinct aircraft present per local hour."""

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        """24 rows {hour, is_fully_covered, positions, observed} for the day."""

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        """{by_type: [...], by_country: [...]} for the day; no operator, no owner."""


class DbSource:
    """Reads the mart directly over psycopg. In production it connects as the
    read-only `flights_ro` role; it is also the live fallback when the API is
    down, and the backend the API itself wraps."""

    def __init__(self, dsn: str, h3_resolution: int = 5) -> None:
        self._dsn = dsn
        self._res = h3_resolution

    def _rows(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
        import psycopg  # imported lazily so the module loads without a DB driver

        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, params or {})
            return cur.fetchall()

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        (lo, hi), = self._rows(queries.DATE_RANGE_SQL)
        return (sk_to_date(lo), sk_to_date(hi))

    def default_day(self) -> dt.date | None:
        (d,), = self._rows(queries.DEFAULT_DAY_SQL)   # a date, or None if no full day
        if d is not None:
            return d
        return self.date_range()[1]                   # fall back to the latest day

    def kpis(self) -> dict[str, Any]:
        row, = self._rows(queries.KPIS_SQL)
        keys = ("positions", "transits", "distinct_aircraft", "days", "catalog_coverage_pct")
        return {k: (int(v) if v is not None else None) for k, v in zip(keys, row)}

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        got = {int(h): int(n) for h, n in self._rows(queries.DAY_CURVE_SQL, {"day_sk": day_sk(day)})}
        return [{"hour": h, "aircraft": got.get(h, 0)} for h in range(24)]

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        got = {int(h): (bool(fc), int(pos)) for h, fc, pos in
               self._rows(queries.DAY_COVERAGE_SQL, {"day": day})}
        out = []
        for h in range(24):
            fc, pos = got.get(h, (False, 0))
            out.append({"hour": h, "is_fully_covered": fc, "positions": pos, "observed": h in got})
        return out

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        p = {"day_sk": day_sk(day)}
        return {
            "by_type": [{"label": t, "positions": int(n)}
                        for t, n in self._rows(queries.DAY_TYPE_SQL, p)],
            "by_country": [{"label": c, "positions": int(n)}
                           for c, n in self._rows(queries.DAY_COUNTRY_SQL, p)],
        }

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        points = self._rows(queries.DAY_POSITIONS_SQL, {"day_sk": day_sk(day)})
        return bin_h3(points, self._res)


class ApiSource:
    """Reads the read-only API over HTTP — the live dashboard's primary backend.
    `client` accepts any object with a `.get(url)` returning a response that has
    `.raise_for_status()` and `.json()` (an `httpx.Client` in production, a
    FastAPI `TestClient` in tests); without one it uses `httpx` directly."""

    def __init__(self, base_url: str = "", timeout: float = 10.0, client: Any = None) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    def _get(self, path: str) -> dict[str, Any]:
        url = self._base + path
        if self._client is not None:
            resp = self._client.get(url)
        else:
            import httpx

            resp = httpx.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        d = self._get("/meta")["date_range"]
        lo = dt.date.fromisoformat(d["min"]) if d["min"] else None
        hi = dt.date.fromisoformat(d["max"]) if d["max"] else None
        return (lo, hi)

    def default_day(self) -> dt.date | None:
        d = self._get("/meta")["default_day"]
        return dt.date.fromisoformat(d) if d else None

    def kpis(self) -> dict[str, Any]:
        return self._get("/meta")["kpis"]

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        return self._get(f"/day/{day.isoformat()}/map")["cells"]

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        return self._get(f"/day/{day.isoformat()}/curve")["curve"]

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        return self._get(f"/day/{day.isoformat()}/coverage")["coverage"]

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        d = self._get(f"/day/{day.isoformat()}/breakdown")
        return {"by_type": d["by_type"], "by_country": d["by_country"]}


class SnapshotSource:
    """Reads a frozen SQLite snapshot (built by build_snapshot.py) — the offline
    form's backend. No server, no live database: the whole dataset is the one
    file. The aggregates were pre-computed at build time, so the queries here are
    simple reads of per-day tables. Mirrors the DbSource/ApiSource shapes exactly."""

    def __init__(self, path: str) -> None:
        self._path = path

    def _conn(self):
        import sqlite3

        return sqlite3.connect(self._path)

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        with self._conn() as c:
            row = c.execute("SELECT date_min, date_max FROM meta").fetchone()
        if not row or row[0] is None:
            return (None, None)
        return (dt.date.fromisoformat(row[0]), dt.date.fromisoformat(row[1]))

    def default_day(self) -> dt.date | None:
        with self._conn() as c:
            row = c.execute("SELECT default_day FROM meta").fetchone()
        return dt.date.fromisoformat(row[0]) if row and row[0] else None

    def kpis(self) -> dict[str, Any]:
        keys = ("positions", "transits", "distinct_aircraft", "days", "catalog_coverage_pct")
        with self._conn() as c:
            row = c.execute(
                "SELECT kpi_positions, kpi_transits, kpi_distinct_aircraft, "
                "kpi_days, kpi_catalog_coverage_pct FROM meta"
            ).fetchone()
        if not row:
            return {k: None for k in keys}
        return {k: (int(v) if v is not None else None) for k, v in zip(keys, row)}

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT hour, aircraft FROM day_curve WHERE day = ?", (day.isoformat(),)
            ).fetchall()
        got = {int(h): int(a) for h, a in rows}
        return [{"hour": h, "aircraft": got.get(h, 0)} for h in range(24)]

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT hour, is_fully_covered, positions, observed "
                "FROM day_coverage WHERE day = ?", (day.isoformat(),)
            ).fetchall()
        got = {int(h): (bool(f), int(p), bool(o)) for h, f, p, o in rows}
        out = []
        for h in range(24):
            f, p, o = got.get(h, (False, 0, False))
            out.append({"hour": h, "is_fully_covered": f, "positions": p, "observed": o})
        return out

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT kind, label, positions FROM day_breakdown WHERE day = ? "
                "ORDER BY positions DESC", (day.isoformat(),)
            ).fetchall()
        return {
            "by_type": [{"label": l, "positions": int(p)} for k, l, p in rows if k == "type"],
            "by_country": [{"label": l, "positions": int(p)} for k, l, p in rows if k == "country"],
        }

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT h3, lat, lon, count FROM day_map WHERE day = ?", (day.isoformat(),)
            ).fetchall()
        return [{"h3": h, "lat": lat, "lon": lon, "count": int(cnt)} for h, lat, lon, cnt in rows]


class FallbackSource:
    """Tries a primary source and, when a call raises, falls back to a secondary
    one. Used live with the API as primary and a direct read-only DB connection
    as the fallback, so the dashboard still renders if the API is down."""

    def __init__(self, primary: Any, secondary: Any) -> None:
        self._primary = primary
        self._secondary = secondary

    def _call(self, name: str, *args: Any) -> Any:
        try:
            return getattr(self._primary, name)(*args)
        except Exception:
            return getattr(self._secondary, name)(*args)

    def date_range(self) -> tuple[dt.date | None, dt.date | None]:
        return self._call("date_range")

    def default_day(self) -> dt.date | None:
        return self._call("default_day")

    def kpis(self) -> dict[str, Any]:
        return self._call("kpis")

    def day_map(self, day: dt.date) -> list[dict[str, Any]]:
        return self._call("day_map", day)

    def day_curve(self, day: dt.date) -> list[dict[str, Any]]:
        return self._call("day_curve", day)

    def day_coverage(self, day: dt.date) -> list[dict[str, Any]]:
        return self._call("day_coverage", day)

    def day_breakdown(self, day: dt.date) -> dict[str, list[dict[str, Any]]]:
        return self._call("day_breakdown", day)


def bin_h3(points: list[tuple], resolution: int) -> list[dict[str, Any]]:
    """Aggregate (lat, lon) rows into H3 cells, returning each cell's id, centre
    and count. Pre-aggregating here keeps the raw points out of every response."""
    import h3  # h3 v4 API; imported lazily so non-map callers need no h3

    counts: dict[str, int] = {}
    for lat, lon in points:
        cell = h3.latlng_to_cell(float(lat), float(lon), resolution)
        counts[cell] = counts.get(cell, 0) + 1

    cells = []
    for cell, n in counts.items():
        lat, lon = h3.cell_to_latlng(cell)
        cells.append({"h3": cell, "lat": lat, "lon": lon, "count": n})
    return cells
