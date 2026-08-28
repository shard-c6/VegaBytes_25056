"""
MakeMyTrip Scraper (OTA).

Scrapes non-stop economy fares from MakeMyTrip.
Uses Playwright-stealth as primary, AI DOM parser as fallback.

Owner: Shardul
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

# Placeholder URL. Will be updated once manual inspection is done.
MMT_SEARCH_URL = (
    "https://www.makemytrip.com/flight/search?itinerary={origin}-{destination}-{date}"
    "&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E"
)


@ScraperFactory.register
class MakeMyTripScraper(BaseScraper):
    SOURCE_ID = "makemytrip"
    REQUEST_DELAY = 30.0

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

            # Wait for either the search results or a reasonable timeout
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass

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
                    # Based on the user's older Selenium code, #listing-id is the root container.
                    html_fragment = page.inner_html("#listing-id", timeout=5000)
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
        records = []
        # DEFERRED (see issue #17 follow-up): placeholder selectors always
        # return zero cards, so this intentionally falls through to the AI DOM
        # parser for now — real selectors need live-DOM inspection, using the
        # HTML archive_html() in scrape_route() now saves for offline work.
        fare_cards = page.query_selector_all(".listingCard-placeholder")
        for card in fare_cards:
            try:
                total_text = card.query_selector(".priceSection-placeholder")
                if not total_text:
                    continue
                total_fare = float(
                    total_text.inner_text().replace("₹", "").replace(",", "").strip()
                )
                records.append(
                    FareRecord(
                        route=f"{origin}-{destination}",
                        airline="MakeMyTrip OTA",
                        flight_number=None,
                        cabin_class="economy",
                        departure_date=departure_date,
                        booking_window=booking_window,
                        base_fare=None,
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
