"""
Test the manual-ingest path: a saved HTML page → validated rows in the DB.

This is the egress-proof bridge — a page captured out-of-band (by hand, or any
collector that can reach the live site) is parsed by the real selectors and
persisted exactly like a live scrape. Runs against the committed real-DOM
MakeMyTrip fixture, into a throwaway file-based SQLite DB.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from src import db

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "makemytrip_sample.html"


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    # File-based (not :memory:) so the several connections run_fixture opens
    # all see the same database.
    engine = create_engine(f"sqlite:///{tmp_path / 'ingest.db'}", future=True)
    monkeypatch.setattr(db, "engine", engine)
    yield engine
    engine.dispose()


def test_fixture_persist_writes_real_rows(temp_db):
    from src.scrapers import run_pipeline

    inserted = run_pipeline.run_fixture(
        "makemytrip",
        ("BOM", "BLR"),
        1,
        str(FIXTURE),
        persist=True,
        departure=date(2026, 8, 30),
    )
    assert inserted == 10

    with temp_db.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM scraped_fares")).scalar() == 10
        assert c.execute(text("SELECT status FROM scraper_runs")).scalar() == "success"
        airlines = {r[0] for r in c.execute(text("SELECT DISTINCT airline FROM scraped_fares"))}
        assert airlines == {"Akasa Air", "Air India", "IndiGo"}


def test_fixture_without_persist_returns_zero(temp_db):
    from src.scrapers import run_pipeline

    # persist=False extracts/prints but writes nothing.
    assert run_pipeline.run_fixture("makemytrip", ("BOM", "BLR"), 1, str(FIXTURE)) == 0


def test_fixture_csv_export(tmp_path):
    from src.scrapers import run_pipeline

    out = tmp_path / "fares.csv"
    n = run_pipeline.run_fixture("makemytrip", ("BOM", "BLR"), 1, str(FIXTURE), csv_path=str(out))
    assert n == 0  # csv-only (no persist) returns 0 persisted
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",")[:4] == ["captured_at", "source", "route", "airline"]
    assert len(lines) == 11  # header + 10 fares
    assert "makemytrip,BOM-BLR" in lines[1]
