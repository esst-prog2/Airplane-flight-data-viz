"""
View builders for the dashboard: pure functions that turn the DataSource
aggregates into Plotly figures and a pydeck map. They contain no Streamlit call,
so they can be unit-tested without a Streamlit runtime; app.py wires them to the
page. Charts are Plotly (D5), the map is pydeck H3 hexagons (D2).
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import pydeck as pdk

# centre of the collection box (lat 45-50, lon 12-23) for the initial map view
_VIEW = {"latitude": 47.5, "longitude": 17.5, "zoom": 4.6, "pitch": 40}
# local peak hours, mirroring is_peak_traffic in dim_time_of_day (10:00-18:00)
_PEAK_FROM, _PEAK_TO = 10, 18


def kpi_items(kpis: dict[str, Any]) -> list[tuple[str, str]]:
    """Ordered (label, display value) pairs for the KPI band."""
    def num(v: Any) -> str:
        if v is None:
            return "—"
        return f"{v:,}" if isinstance(v, int) else str(v)

    cov = kpis.get("catalog_coverage_pct")
    return [
        ("Positions", num(kpis.get("positions"))),
        ("Transits", num(kpis.get("transits"))),
        ("Distinct aircraft", num(kpis.get("distinct_aircraft"))),
        ("Days collected", num(kpis.get("days"))),
        ("Catalogue coverage", "—" if cov is None else f"{cov}%"),
    ]


def curve_figure(curve: list[dict[str, Any]]) -> go.Figure:
    """Distinct aircraft present per local hour (24 bars; peak hours highlighted)."""
    hours = [r["hour"] for r in curve]
    colors = ["#2b6cb0" if _PEAK_FROM <= h <= _PEAK_TO else "#a0aec0" for h in hours]
    fig = go.Figure(go.Bar(
        x=hours, y=[r["aircraft"] for r in curve], marker_color=colors,
        hovertemplate="%{x}:00 — %{y} aircraft<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="local hour", yaxis_title="distinct aircraft",
        margin=dict(l=0, r=0, t=10, b=0), height=300,
        xaxis=dict(tickmode="linear", dtick=2),
    )
    return fig


def coverage_figure(coverage: list[dict[str, Any]]) -> go.Figure:
    """Positions per local hour, coloured green when fully covered, red on a gap."""
    hours = [r["hour"] for r in coverage]
    colors = ["#38a169" if r["is_fully_covered"] else "#e53e3e" for r in coverage]
    fig = go.Figure(go.Bar(
        x=hours, y=[r["positions"] for r in coverage], marker_color=colors,
        hovertemplate="%{x}:00 — %{y} positions<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="local hour", yaxis_title="positions landed",
        margin=dict(l=0, r=0, t=10, b=0), height=240,
        xaxis=dict(tickmode="linear", dtick=2),
    )
    return fig


def _hbar(rows: list[dict[str, Any]], title: str) -> go.Figure:
    rows = list(reversed(rows))  # plotly horizontal bars read bottom to top
    fig = go.Figure(go.Bar(
        x=[r["positions"] for r in rows], y=[r["label"] for r in rows],
        orientation="h", marker_color="#2b6cb0",
    ))
    fig.update_layout(title=title, margin=dict(l=0, r=0, t=30, b=0),
                      height=max(200, 22 * len(rows)))
    return fig


def breakdown_figures(breakdown: dict[str, list[dict[str, Any]]]) -> tuple[go.Figure, go.Figure]:
    """Horizontal bar charts for the aircraft-type and country breakdowns."""
    return (_hbar(breakdown["by_type"], "By aircraft type"),
            _hbar(breakdown["by_country"], "By registration country"))


def _ramp(count: int, cmax: int) -> list[int]:
    """An RGBA fill scaled by relative density (cool + low to warm + high)."""
    t = 0.0 if cmax <= 0 else count / cmax
    return [int(60 + t * 195), int(110 + t * 110), int(200 - t * 150), 180]


def map_deck(cells: list[dict[str, Any]]) -> pdk.Deck:
    """3-D H3 hexagon map: taller and warmer cells saw more positions."""
    cmax = max((c["count"] for c in cells), default=0)
    data = [{"h3": c["h3"], "count": c["count"], "color": _ramp(c["count"], cmax)}
            for c in cells]
    layer = pdk.Layer(
        "H3HexagonLayer", data=data, get_hexagon="h3",
        get_fill_color="color", get_elevation="count",
        elevation_scale=12, extruded=True, pickable=True, opacity=0.6,
    )
    return pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(**_VIEW),
        map_style=None,
        tooltip={"text": "{count} positions"},
    )


def partial_day_note(coverage: list[dict[str, Any]]) -> str | None:
    """A caption when the day has unobserved or not-fully-covered hours, else None."""
    missing = [r["hour"] for r in coverage if not r.get("observed", True)]
    partial = [r["hour"] for r in coverage
               if r.get("observed", True) and not r["is_fully_covered"]]
    if not missing and not partial:
        return None
    bits = []
    if missing:
        bits.append(f"{len(missing)} hour(s) with no data")
    if partial:
        bits.append(f"{len(partial)} hour(s) not fully covered")
    return "Partial day: " + ", ".join(bits) + " — see the coverage view below."
