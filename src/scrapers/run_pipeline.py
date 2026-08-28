"""
Pipeline orchestrator — scrape every source × route × booking window,
validate, and persist. This is what makes the pipeline produce real rows
end to end (issue #17).

Usage:
    python -m src.scrapers.run_pipeline

Env:
    DATABASE_URL   defaults to sqlite:///vegabytes.db (see src/db.py)
    HTTP_PROXY     optional rotating residential proxy
    GEMINI_MODEL   optional override for the AI fallback model
    GEMINI_API_KEY required by the AI fallback (src/scrapers/ai_dom_parser.py)
    HEADLESS       "true"/"false", passed through by each scraper

Owner: Shardul
Related Issue: #17
"""

from __future__ import annotations

import os
import time
import traceback
from datetime import date, timedelta

import structlog
from dotenv import load_dotenv

# Explicit imports required to populate the ScraperFactory registry —
# src/scrapers/__init__.py does not import these, so nothing registers
# @ScraperFactory.register unless the module itself is imported somewhere.
import src.scrapers.airindia_direct  # noqa: F401
import src.scrapers.indigo_direct  # noqa: F401
import src.scrapers.makemytrip  # noqa: F401
from src import db
from src.etl.validator import PriceValidator
from src.scrapers.base import ScraperFactory

log = structlog.get_logger()

SOURCES = ["indigo_direct", "airindia_direct", "makemytrip"]
ROUTES = [
    ("DEL", "BOM"),
    ("BLR", "DEL"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("HYD", "DEL"),
]
BOOKING_WINDOWS = [1, 7, 30]
INTER_ROUTE_DELAY_SECONDS = 5.0


def run_source(source_id: str, proxy: str | None) -> None:
    """Scrape every route × booking window for one source and persist results."""
    validator = PriceValidator()

    with db.engine.connect() as conn:
        run_id = db.start_scraper_run(conn, source_id)

    total_scraped = 0
    total_rejected = 0
    error_message: str | None = None
    status = "failed"

    try:
        scraper = ScraperFactory.get(source_id, proxy=proxy)

        for origin, destination in ROUTES:
            for window in BOOKING_WINDOWS:
                departure_date = date.today() + timedelta(days=window)
                route = f"{origin}-{destination}"
                log.info("scraping_route", source=source_id, route=route, window=window)

                try:
                    records = scraper.scrape_route(origin, destination, departure_date, window)
                except Exception as e:
                    log.error(
                        "scrape_route_failed",
                        source=source_id,
                        route=route,
                        window=window,
                        error=str(e),
                    )
                    continue

                valid, rejected = validator.validate_batch(records)
                with db.engine.connect() as conn:
                    total_scraped += db.insert_scraped_fares(conn, valid)
                    total_rejected += db.insert_rejections(conn, source_id, rejected)

                time.sleep(INTER_ROUTE_DELAY_SECONDS)

        status = "success" if total_scraped > 0 else "failed"
        if status == "failed":
            error_message = "zero rows scraped across all routes/windows"
    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"
        log.error("scraper_source_crashed", source=source_id, error=error_message)
        traceback.print_exc()

    with db.engine.connect() as conn:
        db.finish_scraper_run(conn, run_id, status, total_scraped, total_rejected, error_message)

    log.info(
        "source_run_complete",
        source=source_id,
        status=status,
        rows_scraped=total_scraped,
        rows_rejected=total_rejected,
    )


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )
    load_dotenv()
    db.ensure_schema()

    proxy = os.getenv("HTTP_PROXY")
    if proxy:
        log.info("using_proxy", proxy=proxy)

    for source_id in SOURCES:
        try:
            run_source(source_id, proxy)
        except Exception:
            log.error("source_run_uncaught_error", source=source_id)
            traceback.print_exc()


if __name__ == "__main__":
    main()
