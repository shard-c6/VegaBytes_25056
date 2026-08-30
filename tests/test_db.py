"""
Tests for the SQLAlchemy Core persistence layer — Issue #17.
Run: DATABASE_URL=sqlite:///:memory: pytest tests/test_db.py -v

Uses a fresh in-memory SQLite database per test (module fixture below
resets src.db's module-level engine/metadata) rather than mocking, since
the whole point is exercising real SQL against real tables.
"""

from datetime import date

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src import db
from src.scrapers.base import FareRecord


@pytest.fixture(autouse=True)
def fresh_engine(monkeypatch):
    """Point src.db at a throwaway in-memory SQLite DB for each test."""
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:", future=True)
    monkeypatch.setattr(db, "engine", engine)
    db.ensure_schema()
    yield
    engine.dispose()


def make_record(**kwargs) -> FareRecord:
    defaults = dict(
        route="DEL-BOM",
        airline="IndiGo",
        flight_number="6E-123",
        cabin_class="economy",
        departure_date=date(2026, 9, 1),
        booking_window=7,
        base_fare=3500.0,
        fuel_surcharge=None,
        udf=None,
        psf=None,
        gst=None,
        total_fare=4200.0,
        source="indigo_direct",
        source_url="https://example.com",
        raw_html_path="data/raw/indigo_direct/DEL-BOM/x.html.gz",
    )
    defaults.update(kwargs)
    return FareRecord(**defaults)  # type: ignore[arg-type]


def test_ensure_schema_seeds_routes():
    from src.config import ROUTES

    with db.engine.connect() as conn:
        rows = list(conn.execute(select(db.routes.c.origin, db.routes.c.destination)))
    assert ("DEL", "BOM") in rows
    # Seeds exactly the config basket (single source of truth), no drift.
    assert len(rows) == len(ROUTES)
    assert set(rows) == set(ROUTES)


def test_route_label_is_generated():
    with db.engine.connect() as conn:
        row = conn.execute(
            select(db.routes.c.label).where(
                db.routes.c.origin == "DEL", db.routes.c.destination == "BOM"
            )
        ).first()
    assert row[0] == "DEL-BOM"


def test_duplicate_route_rejected():
    with db.engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(insert(db.routes).values(origin="DEL", destination="BOM"))
            conn.commit()


def test_insert_scraped_fares_round_trips():
    with db.engine.connect() as conn:
        n = db.insert_scraped_fares(conn, [make_record()])
        assert n == 1
        row = conn.execute(select(db.scraped_fares)).first()
    assert row.total_fare == 4200.0
    assert row.raw_html_path == "data/raw/indigo_direct/DEL-BOM/x.html.gz"


def test_insert_scraped_fares_skips_unknown_route():
    with db.engine.connect() as conn:
        n = db.insert_scraped_fares(conn, [make_record(route="XXX-YYY")])
        assert n == 0


def test_insert_rejections_round_trips():
    with db.engine.connect() as conn:
        n = db.insert_rejections(
            conn,
            "indigo_direct",
            [{"route": "DEL-BOM", "source": "indigo_direct", "rejection_reason": "too high"}],
        )
        assert n == 1
        row = conn.execute(select(db.data_quality_log)).first()
    assert row.rejection_reason == "too high"


def test_scraper_run_lifecycle():
    with db.engine.connect() as conn:
        run_id = db.start_scraper_run(conn, "indigo_direct")
        db.finish_scraper_run(conn, run_id, "success", rows_scraped=3, rows_rejected=1)
        row = conn.execute(select(db.scraper_runs).where(db.scraper_runs.c.id == run_id)).first()
    assert row.status == "success"
    assert row.rows_scraped == 3
    assert row.finished_at is not None
