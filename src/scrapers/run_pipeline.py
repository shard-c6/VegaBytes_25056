"""
Pipeline orchestrator — scrape every source × route × booking window,
validate, and persist. This is what makes the pipeline produce real rows
end to end (issue #17).

Usage:
    python -m src.scrapers.run_pipeline
    python -m src.scrapers.run_pipeline --source indigo_direct --route DEL-BOM --window 7
    python -m src.scrapers.run_pipeline --fixture data/raw/indigo_direct/DEL-BOM/x.html.gz \
        --source indigo_direct --route DEL-BOM --window 7   # offline, no browser

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

import argparse
import csv
import gzip
import os
import pathlib
import time
import traceback
from datetime import UTC, date, datetime, timedelta

import structlog
from dotenv import load_dotenv

# Must run before the imports below: src.db reads DATABASE_URL at module
# scope, and ai_dom_parser.AIdomParser.model_name reads GEMINI_MODEL as a
# dataclass field default evaluated at import time — a .env-only value
# would otherwise be silently ignored.
load_dotenv()

# Explicit imports required to populate the ScraperFactory registry —
# src/scrapers/__init__.py does not import these, so nothing registers
# @ScraperFactory.register unless the module itself is imported somewhere.
import src.scrapers.airindia_direct  # noqa: E402,F401
import src.scrapers.indigo_direct  # noqa: E402,F401
import src.scrapers.makemytrip  # noqa: E402,F401
from src import config, db  # noqa: E402
from src.etl.validator import PriceValidator  # noqa: E402
from src.scrapers.base import ScraperFactory  # noqa: E402

log = structlog.get_logger()

SOURCES = ["indigo_direct", "airindia_direct", "makemytrip"]
# Route basket and advance-purchase windows come from src/config (single source
# of truth, PS-aligned) so the scraper and the DB seed can never drift apart.
ROUTES = config.ROUTES
BOOKING_WINDOWS = config.BOOKING_WINDOWS
INTER_ROUTE_DELAY_SECONDS = 5.0


def run_source(
    source_id: str,
    proxy: str | None,
    routes: list[tuple[str, str]] | None = None,
    windows: list[int] | None = None,
) -> None:
    """Scrape every route × booking window for one source and persist results."""
    routes = routes or ROUTES
    windows = windows or BOOKING_WINDOWS
    validator = PriceValidator()

    with db.engine.connect() as conn:
        run_id = db.start_scraper_run(conn, source_id)

    total_scraped = 0
    total_rejected = 0
    error_message: str | None = None
    status = "failed"

    try:
        scraper = ScraperFactory.get(source_id, proxy=proxy)

        for origin, destination in routes:
            for window in windows:
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
                finally:
                    # Polite-scraping delay must apply on failure too, or a
                    # crashing route gets hit again immediately next loop.
                    time.sleep(INTER_ROUTE_DELAY_SECONDS)

                valid, rejected = validator.validate_batch(records)
                with db.engine.connect() as conn:
                    total_scraped += db.insert_scraped_fares(conn, valid)
                    total_rejected += db.insert_rejections(conn, source_id, rejected)

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


def _parse_route(route: str) -> tuple[str, str]:
    origin, _, destination = route.partition("-")
    if not origin or not destination:
        raise argparse.ArgumentTypeError(f"route must look like DEL-BOM, got {route!r}")
    return origin.upper(), destination.upper()


CSV_COLUMNS = [
    "captured_at",
    "source",
    "route",
    "airline",
    "flight_number",
    "cabin_class",
    "booking_window",
    "departure_date",
    "base_fare",
    "fuel_surcharge",
    "udf",
    "psf",
    "gst",
    "total_fare",
    "source_url",
]


def write_csv(records: list, csv_path: str, append: bool = False) -> int:
    """
    Write fare records to a CSV — the offline fallback the demo runbook's
    Layer 3 relies on (a portable snapshot that needs no DB or network).

    `captured_at` is stamped at export time; for a hand-saved page that is the
    ingest moment, not a precise scrape instant — good enough for a fallback
    snapshot, and honest about what it is.
    """
    path = pathlib.Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    mode = "a" if append and path.exists() else "w"
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if mode == "w":
            writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "captured_at": now,
                    "source": r.source,
                    "route": r.route,
                    "airline": r.airline,
                    "flight_number": r.flight_number,
                    "cabin_class": r.cabin_class,
                    "booking_window": r.booking_window,
                    "departure_date": r.departure_date.isoformat(),
                    "base_fare": r.base_fare,
                    "fuel_surcharge": r.fuel_surcharge,
                    "udf": r.udf,
                    "psf": r.psf,
                    "gst": r.gst,
                    "total_fare": r.total_fare,
                    "source_url": r.source_url,
                }
            )
    log.info("csv_written", path=str(path), rows=len(records), mode=mode)
    return len(records)


def run_fixture(
    source_id: str,
    route: tuple[str, str],
    window: int,
    fixture_path: str,
    persist: bool = False,
    departure: date | None = None,
    csv_path: str | None = None,
    csv_append: bool = False,
) -> int:
    """
    Extract one source's fares from a saved HTML file (plain or .gz) — no
    browser, no network.

    Two uses:
      • selector development (persist=False): prints the FareRecords the
        selectors would produce, the fast loop for tuning them offline.
      • manual ingest (persist=True): validates and writes the rows to the DB,
        exactly like a live scrape. Turns a page captured by hand (or by any
        out-of-band collector) into real, timestamped rows — the egress-proof
        path to real data when the live site can't be reached from here.

    Returns the number of rows persisted (0 when persist=False).
    """
    path = pathlib.Path(fixture_path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        html = f.read()

    scraper = ScraperFactory.get(source_id)
    origin, destination = route
    departure_date = departure or (date.today() + timedelta(days=window))
    records = scraper.extract_fares_from_html(
        html,
        origin,
        destination,
        departure_date,
        window,
        source_url=str(path),
    )
    log.info("fixture_extract_complete", source=source_id, records=len(records))
    for r in records:
        print(
            f"  {r.airline:12} {r.flight_number or '-':10} ₹{r.total_fare:>9,.0f}  ({r.cabin_class})"
        )

    if csv_path:
        write_csv(records, csv_path, append=csv_append)

    if not persist:
        return 0

    db.ensure_schema()
    validator = PriceValidator()
    valid, rejected = validator.validate_batch(records)
    with db.engine.connect() as conn:
        run_id = db.start_scraper_run(conn, source_id)
    with db.engine.connect() as conn:
        inserted = db.insert_scraped_fares(conn, valid)
        rejected_n = db.insert_rejections(conn, source_id, rejected)
    with db.engine.connect() as conn:
        db.finish_scraper_run(
            conn,
            run_id,
            "success" if inserted else "failed",
            inserted,
            rejected_n,
            None if inserted else "zero rows persisted from fixture",
        )
    log.info(
        "fixture_persist_complete",
        source=source_id,
        inserted=inserted,
        rejected=rejected_n,
    )
    return inserted


def main(argv: list[str] | None = None) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    parser = argparse.ArgumentParser(description="VegaBytes scraper pipeline")
    parser.add_argument(
        "--source",
        choices=SOURCES,
        action="append",
        help="Limit to this source (repeatable). Default: all.",
    )
    parser.add_argument(
        "--route",
        type=_parse_route,
        action="append",
        help="Limit to this route, e.g. DEL-BOM (repeatable). Default: all.",
    )
    parser.add_argument(
        "--window",
        type=int,
        action="append",
        help="Limit to this booking window in days (repeatable). Default: 1,7,30.",
    )
    parser.add_argument(
        "--fixture",
        help="Extract from a saved HTML file offline (no browser). "
        "Requires exactly one --source/--route/--window.",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="With --fixture: validate and write the extracted rows to the DB "
        "(manual ingest of a hand-captured page), not just print them.",
    )
    parser.add_argument(
        "--departure",
        type=date.fromisoformat,
        help="With --fixture: the flight's departure date (YYYY-MM-DD). "
        "Defaults to today + window; set it for an accurately captured page.",
    )
    parser.add_argument(
        "--csv",
        help="With --fixture: also write the extracted rows to this CSV "
        "(offline fallback). Combine with --csv-append to accumulate routes.",
    )
    parser.add_argument(
        "--csv-append",
        action="store_true",
        help="With --csv: append to the file (no repeated header) instead of "
        "overwriting — build one combined CSV across sources/routes.",
    )
    parser.add_argument(
        "--print-urls",
        action="store_true",
        help="Print the live search URL each source would hit for every "
        "route × window, then exit. No scraping — validate the URL templates "
        "in a browser before a live run.",
    )
    args = parser.parse_args(argv)

    sources = args.source or SOURCES
    routes = args.route or ROUTES
    windows = args.window or BOOKING_WINDOWS

    if args.print_urls:
        for source_id in sources:
            scraper = ScraperFactory.get(source_id)
            for origin, destination in routes:
                for window in windows:
                    dep = date.today() + timedelta(days=window)
                    print(
                        f"{source_id:16} {origin}-{destination} T+{window:<2} {scraper.build_url(origin, destination, dep)}"
                    )
        return

    if args.fixture:
        if not (len(sources) == 1 and len(routes) == 1 and len(windows) == 1):
            parser.error("--fixture needs exactly one --source, one --route and one --window")
        run_fixture(
            sources[0],
            routes[0],
            windows[0],
            args.fixture,
            persist=args.persist,
            departure=args.departure,
            csv_path=args.csv,
            csv_append=args.csv_append,
        )
        return
    if args.persist or args.departure or args.csv:
        parser.error("--persist/--departure/--csv only apply with --fixture")

    db.ensure_schema()

    proxy = os.getenv("HTTP_PROXY")
    if proxy:
        # Never log the raw URL — it may embed proxy credentials.
        log.info("using_proxy", configured=True)

    for source_id in sources:
        try:
            run_source(source_id, proxy, routes, windows)
        except Exception:
            log.error("source_run_uncaught_error", source=source_id)
            traceback.print_exc()


if __name__ == "__main__":
    main()
