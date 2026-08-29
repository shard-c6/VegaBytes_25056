"""
Offline regression tests for the MakeMyTrip selector path.

Runs against a fixture trimmed from a REAL MakeMyTrip BOM-BLR results page
(saved via DevTools, icons/scripts stripped) — no browser, no network. Guards
that the captured data-test selectors keep extracting the real carriers and
standard fares, and do NOT pick up the coupon-discount text.
"""

from __future__ import annotations

import pathlib
from datetime import date

from src.scrapers.makemytrip import MakeMyTripScraper

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "makemytrip_sample.html"


def _extract():
    html = FIXTURE.read_text(encoding="utf-8")
    return MakeMyTripScraper().extract_fares_from_html(
        html,
        origin="BOM",
        destination="BLR",
        departure_date=date(2026, 8, 30),
        booking_window=1,
        source_url="https://www.makemytrip.com/",
    )


def test_extracts_all_real_cards():
    # The saved page had exactly 10 flight cards.
    assert len(_extract()) == 10


def test_real_fares_are_pre_coupon_standard_prices():
    fares = [r.total_fare for r in _extract()]
    assert fares == [6496.0, 6517.0, 6517.0, 6487.0, 6487.0, 6487.0, 6487.0, 6570.0, 6741.0, 6914.0]


def test_real_per_card_airlines():
    airlines = [r.airline for r in _extract()]
    assert airlines == [
        "Akasa Air",
        "Air India",
        "Air India",
        "IndiGo",
        "IndiGo",
        "IndiGo",
        "IndiGo",
        "IndiGo",
        "Air India",
        "IndiGo",
    ]
    # OTA carriers are read per-card, never the bogus "MakeMyTrip OTA" literal.
    assert "MakeMyTrip OTA" not in airlines


def test_route_and_source():
    r = _extract()[0]
    assert r.source == "makemytrip"
    assert r.route == "BOM-BLR"
