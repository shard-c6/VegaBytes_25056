"""
Tests that route/date are substituted dynamically into each source's search
URL — the PS requirement that the same scraper covers every route by changing
only the URL. Pure string building, no browser/network.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.scrapers.airindia_direct import AirIndiaDirectScraper
from src.scrapers.indigo_direct import IndigoDirectScraper
from src.scrapers.makemytrip import MakeMyTripScraper

DEP = date(2026, 9, 15)


def test_indigo_url_has_route_and_iso_date():
    url = IndigoDirectScraper().build_url("DEL", "CCU", DEP)
    assert "origin=DEL" in url and "destination=CCU" in url
    assert "departure=2026-09-15" in url  # %Y-%m-%d


def test_makemytrip_url_has_route_and_ddmmyyyy_date():
    url = MakeMyTripScraper().build_url("BLR", "HYD", DEP)
    assert "itinerary=BLR-HYD-15/09/2026" in url  # %d/%m/%Y


def test_airindia_url_has_route_and_dashed_date():
    url = AirIndiaDirectScraper().build_url("MAA", "DEL", DEP)
    assert "origin=MAA" in url and "destination=DEL" in url
    assert "date=15-09-2026" in url  # %d-%m-%Y


@pytest.mark.parametrize("origin,destination", [("DEL", "BOM"), ("BOM", "BLR"), ("MAA", "DEL")])
def test_same_scraper_covers_every_route(origin, destination):
    # One scraper instance builds a correct URL for any route — no per-route code.
    url = IndigoDirectScraper().build_url(origin, destination, DEP)
    assert f"origin={origin}" in url and f"destination={destination}" in url
