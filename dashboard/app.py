"""
Streamlit dashboard over the mart (see the dashboard-views spec). Thin wiring:
pick a data source, let the viewer choose a local day, and render the five views
built in views.py. Run locally with:

    streamlit run dashboard/app.py

Data source, first match wins: DASHBOARD_API_URL -> the read-only API;
otherwise DATABASE_URL -> a direct read-only database connection. The
frozen-snapshot source is added in chunk 4.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import streamlit as st

# `streamlit run dashboard/app.py` executes this file as a top-level script, so
# relative imports would fail; put the repo root on sys.path and import the
# package absolutely (the package's own relative imports then resolve normally).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import views
from dashboard.datasource import ApiSource, DbSource


def make_source():
    api_url = os.environ.get("DASHBOARD_API_URL")
    if api_url:
        return ApiSource(api_url)
    return DbSource(os.environ["DATABASE_URL"])


@st.cache_data(ttl=600)
def load_meta() -> tuple[str | None, str | None, dict]:
    src = make_source()
    lo, hi = src.date_range()
    return (lo.isoformat() if lo else None, hi.isoformat() if hi else None, src.kpis())


@st.cache_data(ttl=600)
def load_day(day_iso: str) -> dict:
    src = make_source()
    day = dt.date.fromisoformat(day_iso)
    return {
        "map": src.day_map(day),
        "curve": src.day_curve(day),
        "coverage": src.day_coverage(day),
        "breakdown": src.day_breakdown(day),
    }


def main() -> None:
    st.set_page_config(page_title="Central European air traffic", layout="wide")
    st.title("Central European air traffic")
    st.caption("A queryable history built from OpenSky snapshots over a fixed "
               "Central European box.")

    lo_iso, hi_iso, kpis = load_meta()
    if not lo_iso or not hi_iso:
        st.warning("No data in the mart yet.")
        return

    cols = st.columns(len(views.kpi_items(kpis)))
    for col, (label, value) in zip(cols, views.kpi_items(kpis)):
        col.metric(label, value)

    lo, hi = dt.date.fromisoformat(lo_iso), dt.date.fromisoformat(hi_iso)
    picked = st.date_input("Day (local time)", value=hi, min_value=lo, max_value=hi)
    day = picked[0] if isinstance(picked, tuple) else picked

    data = load_day(day.isoformat())

    note = views.partial_day_note(data["coverage"])
    if note:
        st.info(note)

    st.subheader("Traffic density")
    st.pydeck_chart(views.map_deck(data["map"]))

    left, right = st.columns(2)
    with left:
        st.subheader("Daily traffic curve")
        st.plotly_chart(views.curve_figure(data["curve"]), width="stretch")
    with right:
        st.subheader("Collection coverage")
        st.plotly_chart(views.coverage_figure(data["coverage"]), width="stretch")

    st.subheader("Breakdown")
    type_fig, country_fig = views.breakdown_figures(data["breakdown"])
    c1, c2 = st.columns(2)
    c1.plotly_chart(type_fig, width="stretch")
    c2.plotly_chart(country_fig, width="stretch")
    st.caption("Operator is known for only ~1/3 of traffic, so it is not broken "
               "out; owner is never shown. Type and country come from the "
               "aircraft catalogue.")


main()
