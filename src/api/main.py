"""
VegaBytes REST API — Secure data layer for NSO/RBI consumption.

Endpoints:
    GET /api/v1/index              - Latest APIx index value
    GET /api/v1/index/history      - Historical index series
    GET /api/v1/fares              - Raw fare data (paginated)
    GET /api/v1/pipeline/status    - Pipeline health for monitoring dashboard
    GET /health                    - Liveness probe

Owner: Mufeed
Related Issue: #6
"""

from __future__ import annotations

from datetime import date

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = structlog.get_logger()

app = FastAPI(
    title="VegaBytes APIx — Airfare Price Index API",
    description=(
        "Real-time Airfare Price Index (APIx) for NSO/RBI consumption. "
        "SIH PS 26056 — Team VegaBytes."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO Mufeed: restrict to NSO/RBI domains in production
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Response Models ───────────────────────────────────────


class IndexValueResponse(BaseModel):
    index_date: date
    apix_value: float
    base_period: date
    routes_included: int
    notes: str


class PipelineStatusResponse(BaseModel):
    last_scrape: str | None
    success_rate_24h: float | None
    total_fares_collected: int
    data_freshness: str  # "fresh" | "stale" | "critical"


# ── Endpoints ─────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/index", response_model=IndexValueResponse)
async def get_latest_index():
    """Return the most recently computed APIx value."""
    # TODO Mufeed: query DB for latest row in index_values table
    raise HTTPException(status_code=501, detail="Not yet implemented — see Issue #6")


@app.get("/api/v1/index/history")
async def get_index_history(
    from_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    """Return APIx time series between two dates."""
    if (to_date - from_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")
    # TODO Mufeed: query index_values WHERE index_date BETWEEN from_date AND to_date
    return {"data": [], "from_date": from_date, "to_date": to_date}


@app.get("/api/v1/fares")
async def get_fares(
    route: str | None = Query(None, description="e.g. DEL-BOM"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
):
    """Return paginated raw fare records."""
    # TODO Mufeed: query scraped_fares with filters
    return {"data": [], "page": page, "page_size": page_size, "total": 0}


@app.get("/api/v1/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status():
    """Return current pipeline health — used by monitoring dashboard."""
    # TODO Mufeed + Mukta: query scraper_runs table for latest status
    return PipelineStatusResponse(
        last_scrape=None,
        success_rate_24h=None,
        total_fares_collected=0,
        data_freshness="critical",
    )
