"""
Tests for the pure view builders (dashboard/views.py): they turn DataSource
aggregates into Plotly figures and a pydeck map, with no Streamlit runtime, so
they can be checked directly. The Streamlit wiring in app.py is verified by
running it; here we pin the figure shapes and the gap/partial logic.
"""

import plotly.graph_objects as go
import pydeck as pdk

from dashboard import views

CURVE = [{"hour": h, "aircraft": h * 10} for h in range(24)]
COVERAGE_OK = [{"hour": h, "is_fully_covered": True, "positions": 100, "observed": True}
               for h in range(24)]
# hours 10,11 fully covered; hour 13 has data but not a full hour; the rest no data
COVERAGE_MIX = [{"hour": h,
                 "is_fully_covered": h in (10, 11),
                 "positions": 100 if h in (10, 11, 13) else 0,
                 "observed": h != 5}
                for h in range(24)]
BREAKDOWN = {"by_type": [{"label": "B738", "positions": 10},
                         {"label": "A320", "positions": 5}],
             "by_country": [{"label": "Hungary", "positions": 8}]}
CELLS = [{"h3": "851e15a7fffffff", "lat": 48.0, "lon": 16.5, "count": 100},
         {"h3": "851e1597fffffff", "lat": 47.0, "lon": 17.0, "count": 10}]


def test_kpi_items_labels_and_formatting():
    items = dict(views.kpi_items(
        {"positions": 1000, "transits": 50, "distinct_aircraft": 30,
         "days": 12, "catalog_coverage_pct": 87}))
    assert items["Positions"] == "1,000"
    assert items["Catalogue coverage"] == "87%"
    assert items["Transits"] == "50"


def test_kpi_items_handle_missing_values():
    items = dict(views.kpi_items({}))
    assert items["Positions"] == "—"
    assert items["Catalogue coverage"] == "—"


def test_curve_figure_has_24_bars_and_a_peak_band():
    fig = views.curve_figure(CURVE)
    assert isinstance(fig, go.Figure)
    assert len(fig.data[0].x) == 24
    assert len(fig.layout.shapes) >= 1   # the shaded peak-window band


def test_coverage_figure_three_state_colours():
    fig = views.coverage_figure(COVERAGE_MIX)
    colours = list(fig.data[0].marker.color)
    assert colours[10] == "#38a169"   # fully covered -> green
    assert colours[13] == "#e53e3e"   # data but not a full hour -> red
    assert colours[0] == "#718096"    # no data -> grey
    assert len(fig.data[0].y) == 24   # all 24 hours shown


def test_breakdown_returns_two_figures():
    type_fig, country_fig = views.breakdown_figures(BREAKDOWN)
    assert isinstance(type_fig, go.Figure)
    assert isinstance(country_fig, go.Figure)


def test_map_deck_one_layer_over_all_cells():
    deck = views.map_deck(CELLS)
    assert isinstance(deck, pdk.Deck)
    assert len(deck.layers) == 1
    assert len(deck.layers[0].data) == 2


def test_partial_day_note():
    assert views.partial_day_note(COVERAGE_OK) is None
    note = views.partial_day_note(COVERAGE_MIX)
    assert note and "hour" in note
