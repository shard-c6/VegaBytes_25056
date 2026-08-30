"""
IndiGo Direct Website Scraper — Primary Source.

Scrapes non-stop economy fares from www.goindigo.in.
Selector-primary (see SELECTORS), AI DOM parser as fallback on breakage.

To make the selector path live: inspect a real goindigo.in results page in
Chrome DevTools, then replace the placeholder classes in SELECTORS below.
The gzipped HTML archived by archive_html() on every scrape lets that be done
offline against a saved page — see docs/ for the capture checklist.

Owner: Shardul
Related Issues: #1 (Legal), #4 (Demo), #5 (Tax Separation), #7 (AI Parser), #17
"""

from __future__ import annotations

from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, FareRecord, ScraperFactory

INDIGO_SEARCH_URL = (
    "https://www.goindigo.in/flight-booking.html"
    "?origin={origin}&destination={destination}"
    "&departure={date}&adult=1&child=0&infant=0&tripType=O&cabin=ECONOMY"
)


@ScraperFactory.register
class IndigoDirectScraper(BaseScraper):
    """
    Scraper for IndiGo direct booking site.

    Compliance notes:
    - robots.txt allows /flight-booking.html crawling
    - Rate: <2 req/min enforced via REQUEST_DELAY
    - No PII collected — price data only
    """

    SOURCE_ID = "indigo_direct"
    REQUEST_DELAY = 35.0  # slightly above minimum to be safe
    AIRLINE = "IndiGo"

    # Captured from a real goindigo.in flight-select page (BOM-BLR). Each
    # .fare-accordion is one flight and holds BOTH a business and an economy
    # fare, so total_fare is scoped to .economy-class-item to take the economy
    # "Starts at" price (the lowest economy bucket) and never the business fare.
    SELECTORS = {
        "card": ".fare-accordion",
        "total_fare": ".economy-class-item .selected-fare__fare-price",
        "flight_number": ".flight-number",
    }
    AI_FALLBACK_SELECTOR = ".fare-accordion, .flight-listing, main"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=60, max=180))
    def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str = "economy",
    ) -> list[FareRecord]:
        url = INDIGO_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date=departure_date.strftime("%Y-%m-%d"),
        )
        return self._fetch_and_extract(
            url, origin, destination, departure_date, booking_window, cabin_class
        )
