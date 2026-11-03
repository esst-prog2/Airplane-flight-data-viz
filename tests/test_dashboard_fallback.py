"""
Tests for FallbackSource: it serves from the primary source, and falls back to
the secondary one when a primary call raises (the live API-down case). Uses tiny
stubs, so no database or network is involved.
"""

from dashboard.datasource import FallbackSource


class _Primary:
    def kpis(self):
        return {"positions": 1}

    def day_curve(self, day):
        return ["primary"]


class _PrimaryDown:
    def kpis(self):
        raise RuntimeError("API unreachable")

    def day_curve(self, day):
        raise RuntimeError("API unreachable")


class _Secondary:
    def kpis(self):
        return {"positions": 99}

    def day_curve(self, day):
        return ["secondary"]


def test_uses_primary_when_it_works():
    fs = FallbackSource(_Primary(), _Secondary())
    assert fs.kpis() == {"positions": 1}
    assert fs.day_curve(None) == ["primary"]


def test_falls_back_to_secondary_when_primary_raises():
    fs = FallbackSource(_PrimaryDown(), _Secondary())
    assert fs.kpis() == {"positions": 99}
    assert fs.day_curve(None) == ["secondary"]
