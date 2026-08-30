"""
Air India Direct Website Scraper.

Scrapes non-stop economy fares from Air India. Selector-primary, AI DOM parser
as fallback on breakage.

To make the selector path live: inspect a real airindia.com results page in
DevTools and replace the placeholder classes in SELECTORS below.

Owner: Shardul
Related Issue: #17
"""

from __future__ import annotations

from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, FareRecord, ScraperFactory


@ScraperFactory.register
class AirIndiaDirectScraper(BaseScraper):
    SOURCE_ID = "airindia_direct"
    REQUEST_DELAY = 30.0
    AIRLINE = "Air India"
    # Placeholder URL. Will be updated once a live airindia.com page is captured.
    SEARCH_URL = (
        "https://www.airindia.com/in/en/book/search-flights.html"
        "?origin={origin}&destination={destination}&date={date}"
    )
    DATE_FORMAT = "%d-%m-%Y"

    # UPDATE THESE after inspecting a live airindia.com results page.
    SELECTORS = {
        "card": ".flight-card",  # UPDATE THIS
        "total_fare": ".price",  # UPDATE THIS
        "flight_number": ".flight-number",  # UPDATE THIS (optional)
    }
    AI_FALLBACK_SELECTOR = ".search-results, .flight-list"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=60, max=180))
    def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str = "economy",
    ) -> list[FareRecord]:
        url = self.build_url(origin, destination, departure_date)
        return self._fetch_and_extract(
            url,
            origin,
            destination,
            departure_date,
            booking_window,
            cabin_class,
            wait_timeout=20_000,
        )
