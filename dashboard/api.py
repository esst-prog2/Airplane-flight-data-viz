"""
Read-only HTTP API over the mart (see the mart-read-api spec). It wraps
`DbSource` on a read-only role and returns per-day aggregates only — never raw
position rows, never the aircraft `owner`. Run with:

    uvicorn dashboard.api:app --host 0.0.0.0 --port 8000

The connection string comes from `DASHBOARD_DSN` (the `flights_ro` DSN in
production), falling back to `DATABASE_URL` for local development.
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import Depends, FastAPI

from .datasource import DbSource

app = FastAPI(title="Flights mart (read-only)", version="1.0")


def get_source() -> DbSource:
    dsn = os.environ.get("DASHBOARD_DSN") or os.environ["DATABASE_URL"]
    return DbSource(dsn, h3_resolution=int(os.environ.get("H3_RESOLUTION", "5")))


@app.get("/meta")
def meta(src: DbSource = Depends(get_source)) -> dict:
    lo, hi = src.date_range()
    return {
        "date_range": {
            "min": lo.isoformat() if lo else None,
            "max": hi.isoformat() if hi else None,
        },
        "kpis": src.kpis(),
    }


@app.get("/day/{day}/map")
def day_map(day: date, src: DbSource = Depends(get_source)) -> dict:
    return {"day": day.isoformat(), "cells": src.day_map(day)}


@app.get("/day/{day}/curve")
def day_curve(day: date, src: DbSource = Depends(get_source)) -> dict:
    return {"day": day.isoformat(), "curve": src.day_curve(day)}


@app.get("/day/{day}/coverage")
def day_coverage(day: date, src: DbSource = Depends(get_source)) -> dict:
    return {"day": day.isoformat(), "coverage": src.day_coverage(day)}


@app.get("/day/{day}/breakdown")
def day_breakdown(day: date, src: DbSource = Depends(get_source)) -> dict:
    return {"day": day.isoformat(), **src.day_breakdown(day)}
