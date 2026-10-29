"""
Tests for the read-only dashboard API (dashboard/api.py) on invented data in a
throwaway database (tests/conftest.py), via FastAPI's TestClient with the data
source pointed at that database. Also checks ApiSource agrees with DbSource.
"""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from test_mart_facts import seed_catalogue_aircraft, land, load_dims, T0

from dashboard import api
from dashboard.datasource import ApiSource, DbSource

# T0 = 2027-01-15 08:00 UTC -> 09:00 Europe/Budapest (winter, +1), same local day
DAY = dt.date(2027, 1, 15)


@pytest.fixture
def client(db, db_url):
    seed_catalogue_aircraft(
        db, "aaaaaa", registration="HA-TST", typecode="B738", model="737-800",
        category_description="Large", country="Hungary", operator="Test Air",
        operator_icao="TST", owner="A Private Owner",
    )
    land(db, 1, "aaaaaa", T0, lat=47.5, lon=19.0)
    land(db, 2, "aaaaaa", T0 + 120, lat=47.6, lon=19.1)
    load_dims(db)
    db.execute("SELECT mart.load_fact_position_snapshot()")

    api.app.dependency_overrides[api.get_source] = lambda: DbSource(db_url)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_meta_reports_range_and_kpis(client):
    m = client.get("/meta").json()
    assert m["date_range"]["min"] == DAY.isoformat()
    assert m["date_range"]["max"] == DAY.isoformat()
    assert m["kpis"]["positions"] >= 1


def test_day_endpoints_have_the_expected_shapes(client):
    assert len(client.get(f"/day/{DAY}/curve").json()["curve"]) == 24
    assert len(client.get(f"/day/{DAY}/coverage").json()["coverage"]) == 24
    cells = client.get(f"/day/{DAY}/map").json()["cells"]
    assert cells and all({"h3", "lat", "lon", "count"} <= c.keys() for c in cells)
    labels = [r["label"] for r in client.get(f"/day/{DAY}/breakdown").json()["by_type"]]
    assert "B738" in labels


def test_map_returns_aggregated_cells_not_raw_points(client):
    # two positions were landed; they bin into a single H3 cell with count 2,
    # so the response is aggregated, not one row per position
    cells = client.get(f"/day/{DAY}/map").json()["cells"]
    assert sum(c["count"] for c in cells) == 2
    assert len(cells) <= 2


def test_empty_day_is_zeroed_not_an_error(client):
    r = client.get("/day/2020-01-01/curve")
    assert r.status_code == 200
    assert all(row["aircraft"] == 0 for row in r.json()["curve"])
    assert client.get("/day/2020-01-01/map").json()["cells"] == []


def test_no_owner_field_is_ever_exposed(client):
    for path in ("/meta", f"/day/{DAY}/map", f"/day/{DAY}/curve",
                 f"/day/{DAY}/coverage", f"/day/{DAY}/breakdown"):
        text = client.get(path).text.lower()
        assert "owner" not in text
        assert "private owner" not in text


def test_apisource_agrees_with_dbsource(client, db_url):
    api_src = ApiSource(base_url="", client=client)   # client = the TestClient
    db_src = DbSource(db_url)
    assert api_src.date_range() == db_src.date_range()
    assert api_src.kpis() == db_src.kpis()
    assert api_src.day_curve(DAY) == db_src.day_curve(DAY)
    assert api_src.day_coverage(DAY) == db_src.day_coverage(DAY)
    assert api_src.day_breakdown(DAY) == db_src.day_breakdown(DAY)
    key = lambda cells: sorted((c["h3"], c["count"]) for c in cells)
    assert key(api_src.day_map(DAY)) == key(db_src.day_map(DAY))
