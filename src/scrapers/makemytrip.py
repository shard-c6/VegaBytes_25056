"""
MakeMyTrip Scraper (OTA).

Scrapes non-stop economy fares from MakeMyTrip. Selector-primary, AI DOM
parser as fallback on breakage.

OTA note: MakeMyTrip sits behind aggressive bot protection (Akamai) and is
best-effort — IndiGo direct is the reliable demo path. Because each result row
is a different carrier, the airline is read per-card via SELECTORS["airline"]
rather than a fixed AIRLINE.

To make the selector path live: inspect a real results page in DevTools and
replace the placeholder classes in SELECTORS below.

Owner: Shardul
Related Issue: #17
"""

from __future__ import annotations

from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, FareRecord, ScraperFactory

# Placeholder URL. Will be updated once manual inspection is done.
MMT_SEARCH_URL = (
    "https://www.makemytrip.com/flight/search?itinerary={origin}-{destination}-{date}"
    "&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E"
)


@ScraperFactory.register
class MakeMyTripScraper(BaseScraper):
    SOURCE_ID = "makemytrip"
    REQUEST_DELAY = 30.0
    AIRLINE = None  # OTA — carrier is per-card, read via SELECTORS["airline"]

    # Captured from a live MakeMyTrip results page via DevTools. We target the
    # stable data-test hooks (breakpoint-independent) rather than styling
    # classes like fontSize18/blackText, which churn on every redesign.
    #   card         [data-test="component-cardBody"] — one per flight
    #   total_fare   [data-test="component-final-fare"] — the standard fare; the
    #                coupon discount lives in a sibling <p class="disc-applied">,
    #                so this is the pre-coupon price we want for the index.
    #   airline      [data-test="component-airline-heading"] — per-card carrier
    SELECTORS = {
        "card": "[data-test='component-cardBody']",
        "total_fare": "[data-test='component-final-fare']",
        "airline": "[data-test='component-airline-heading']",
    }
    AI_FALLBACK_SELECTOR = "#flightsContainer, .listingBodyWrapper"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=60, max=180))
    def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str = "economy",
    ) -> list[FareRecord]:
        url = MMT_SEARCH_URL.format(
            origin=origin,
            destination=destination,
            date=departure_date.strftime("%d/%m/%Y"),  # MMT often uses DD/MM/YYYY in URL
        )
        return self._fetch_and_extract(
            url,
            origin,
            destination,
            departure_date,
            booking_window,
            cabin_class,
            wait_timeout=20_000,
        )
