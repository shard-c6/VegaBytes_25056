"""
Offline regression tests for the MakeMyTrip selector path.

Runs against a committed fixture that mirrors the live MMT DOM (data-test hooks
captured via DevTools) — no browser, no network. Guards that the confirmed
selectors keep extracting the standard fare and, crucially, do NOT pick up the
coupon-discount text that sits in a sibling element.
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


def test_extracts_standard_fares_not_coupon_price():
    records = _extract()
    assert len(records) == 2
    # The pre-coupon fares, not the "12% OFF"/"₹256 OFF" discount amounts.
    assert [r.total_fare for r in records] == [6496.0, 5782.0]


def test_source_and_route_are_set():
    r = _extract()[0]
    assert r.source == "makemytrip"
    assert r.route == "BOM-BLR"


def test_airline_pending_defaults_to_unknown():
    # Documents current state: the airline element is not yet captured, so the
    # OTA rows carry "Unknown" until SELECTORS["airline"] is filled in.
    assert _extract()[0].airline == "Unknown"
