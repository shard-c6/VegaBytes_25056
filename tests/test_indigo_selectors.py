"""
Offline regression tests for the IndiGo selector path.

Runs against a fixture trimmed from a REAL goindigo.in BOM-BLR flight-select
page (first 5 cards, assets stripped) — no browser, no network. Guards that the
captured selectors keep extracting the ECONOMY "Starts at" fare (never the
business fare in the same card) and the flight number.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from src.scrapers.base import SelectorExtractionError
from src.scrapers.indigo_direct import IndigoDirectScraper

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "indigo_sample.html"


def _extract(cabin_class: str = "economy"):
    html = FIXTURE.read_text(encoding="utf-8")
    return IndigoDirectScraper().extract_fares_from_html(
        html,
        origin="BOM",
        destination="BLR",
        departure_date=date(2026, 9, 5),
        booking_window=7,
        cabin_class=cabin_class,
        source_url="https://www.goindigo.in/",
    )


def test_extracts_economy_fares_not_business():
    records = _extract()
    assert len(records) == 5
    # Economy "Starts at" prices — NOT the ₹22,340 business fare in each card.
    assert [r.total_fare for r in records] == [6914.0, 8723.0, 9411.0, 9458.0, 9644.0]
    assert 22340.0 not in [r.total_fare for r in records]


def test_flight_numbers_and_airline():
    records = _extract()
    assert [r.flight_number for r in records][:3] == ["6E5388", "6E6284", "6E6029"]
    assert all(r.airline == "IndiGo" for r in records)
    assert all(r.route == "BOM-BLR" and r.source == "indigo_direct" for r in records)


def test_cabin_class_is_passed_through_not_hardcoded():
    assert _extract(cabin_class="business")[0].cabin_class == "business"


def test_missing_card_selector_raises_breakage():
    with pytest.raises(SelectorExtractionError):
        IndigoDirectScraper().extract_fares_from_html(
            "<html><body><p>no flights here</p></body></html>",
            origin="BOM",
            destination="BLR",
            departure_date=date(2026, 9, 5),
            booking_window=7,
        )
