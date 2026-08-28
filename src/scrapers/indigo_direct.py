"""
IndiGo Direct Website Scraper — Primary Source.

Scrapes non-stop economy fares from www.goindigo.in.
Uses Playwright-stealth as primary, AI DOM parser as fallback.

Owner: Shardul
Related Issues: #1 (Legal), #4 (Demo), #5 (Tax Separation), #7 (AI Parser)
"""

from __future__ import annotations

import os
from datetime import date

import structlog
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from tenacity import retry, stop_after_attempt, wait_exponential

from .ai_dom_parser import AIdomParser
from .base import BaseScraper, FareRecord, ScraperFactory, archive_html

log = structlog.get_logger()

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
    - Rate: 2 req/min enforced via REQUEST_DELAY
    - No PII collected — price data only
    """

    SOURCE_ID = "indigo_direct"
    REQUEST_DELAY = 35.0  # slightly above minimum to be safe

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
        self.log.info("scraping", url=url)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                proxy={"server": self.proxy} if self.proxy else None,
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            page.goto(url, timeout=60_000)
            page.wait_for_load_state("networkidle", timeout=30_000)

            # Archive raw HTML on every scrape (issue #17 A4) — lets selectors
            # be developed offline and makes AI-fallback behavior replayable.
            raw_html_path = None
            try:
                raw_html_path = archive_html(
                    self.SOURCE_ID, f"{origin}-{destination}", page.content()
                )
            except Exception as e:
                self.log.warning("html_archive_failed", error=str(e))

            # ── Primary: CSS selector extraction ──────────────────
            records = self._extract_with_selectors(
                page, origin, destination, departure_date, booking_window
            )

            if not records:
                # ── Fallback: AI DOM Parser ────────────────────────
                self.log.warning("css_selectors_failed", falling_back_to="ai_dom_parser")
                try:
                    html_fragment = page.inner_html(
                        ".flight-listing, .fare-card, main", timeout=5000
                    )
                except Exception:
                    html_fragment = page.evaluate("document.body.innerHTML")
                records = AIdomParser().parse(
                    html_fragment=html_fragment,
                    context={
                        "source": self.SOURCE_ID,
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date,
                        "booking_window": booking_window,
                        "cabin_class": cabin_class,
                    },
                )

            for r in records:
                r.raw_html_path = raw_html_path

            browser.close()
        self._sleep()
        return records

    def _extract_with_selectors(
        self, page, origin, destination, departure_date, booking_window
    ) -> list[FareRecord]:
        """
        Extract fares using CSS selectors.
        DEFERRED (see issue #17 follow-up): placeholder selectors below always
        return zero cards, so every scrape intentionally falls through to the
        AI DOM parser for now. Real selectors need live-DOM inspection this
        session couldn't do; the HTML archived by archive_html() in
        scrape_route() is meant to let that happen offline, without re-scraping.
        Selectors break when IndiGo redesigns — AI parser handles recovery.
        """
        records = []
        # Placeholder — replace with real selectors after DOM inspection
        # Example structure (verify against live site):
        #   .fare-card .base-fare, .fare-card .total-fare, .fare-card .flight-number
        fare_cards = page.query_selector_all(".fare-card")  # UPDATE THIS
        for card in fare_cards:
            try:
                total_text = card.query_selector(".total-price")  # UPDATE THIS
                if not total_text:
                    continue
                total_fare = float(
                    total_text.inner_text().replace("₹", "").replace(",", "").strip()
                )
                records.append(
                    FareRecord(
                        route=f"{origin}-{destination}",
                        airline="IndiGo",
                        flight_number=None,  # TODO: extract flight number
                        cabin_class="economy",
                        departure_date=departure_date,
                        booking_window=booking_window,
                        base_fare=None,  # TODO: extract from fare breakdown page
                        fuel_surcharge=None,
                        udf=None,
                        psf=None,
                        gst=None,
                        total_fare=total_fare,
                        source=self.SOURCE_ID,
                        source_url=page.url,
                    )
                )
            except Exception as e:
                self.log.warning("selector_parse_error", error=str(e))
        return records
