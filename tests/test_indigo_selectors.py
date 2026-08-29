"""
Offline regression tests for CSS-selector extraction.

These run against a committed HTML fixture with NO browser and NO network, so
they gate the selector path deterministically: if a future site redesign (or a
bad edit to SELECTORS) breaks extraction, CI goes red instead of the pipeline
silently emitting zero rows and falling back to the paid AI parser forever.

When real goindigo.in selectors are captured, replace the fixture with a saved
real page and update IndigoDirectScraper.SELECTORS to match — these assertions
then guard the real selectors.
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
        origin="DEL",
        destination="BOM",
        departure_date=date(2026, 9, 5),
        booking_window=7,
        cabin_class=cabin_class,
        source_url="https://www.goindigo.in/",
    )


def test_extracts_parseable_fares_and_skips_sold_out():
    records = _extract()
    # Two priced cards; the third (no price element) is skipped, not fatal.
    assert len(records) == 2
    assert [r.total_fare for r in records] == [4789.0, 5320.0]
    assert [r.flight_number for r in records] == ["6E-2341", "6E-5108"]


def test_airline_and_route_are_set():
    r = _extract()[0]
    assert r.airline == "IndiGo"
    assert r.route == "DEL-BOM"
    assert r.source == "indigo_direct"


def test_cabin_class_is_passed_through_not_hardcoded():
    # Regression: the old scraper accepted cabin_class then hardcoded "economy".
    assert _extract(cabin_class="business")[0].cabin_class == "business"


def test_missing_card_selector_raises_breakage():
    # A page that matches no card must raise (→ AI fallback), not return [].
    with pytest.raises(SelectorExtractionError):
        IndigoDirectScraper().extract_fares_from_html(
            "<html><body><p>no flights here</p></body></html>",
            origin="DEL",
            destination="BOM",
            departure_date=date(2026, 9, 5),
            booking_window=7,
        )
