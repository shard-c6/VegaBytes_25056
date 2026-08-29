"""
Base scraper interface — factory pattern.
All source-specific scrapers must inherit from BaseScraper.

Owner: Shardul (Issue #7 — AI DOM Parser, Issue #4 — Demo Strategy)
"""

from __future__ import annotations

import abc
import gzip
import os
import pathlib
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger()

# Shared desktop UA — kept identical across sources so a site sees one
# consistent client fingerprint rather than three subtly different ones.
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class SelectorExtractionError(Exception):
    """
    Raised when CSS-selector extraction cannot produce a usable result —
    either the card selector matched nothing, or every matched card failed
    to yield a parseable fare. Distinct from a genuine empty result so the
    scraper can fall back to the AI DOM parser on *breakage* specifically,
    instead of on every request (the old ``if not records:`` trigger fired
    the paid Gemini call even when selectors worked and simply found no
    flights).
    """


@dataclass
class FareRecord:
    """Structured fare record matching the DB schema."""

    route: str  # e.g. "DEL-BOM"
    airline: str
    flight_number: str | None
    cabin_class: str  # "economy" | "business"
    departure_date: date
    booking_window: int  # days ahead: 1, 7, 30
    base_fare: float | None
    fuel_surcharge: float | None
    udf: float | None
    psf: float | None
    gst: float | None
    total_fare: float
    source: str  # scraper identifier
    source_url: str | None
    raw_html_path: str | None = None  # gzipped archive of the page HTML, see archive_html()
    extra: dict = field(default_factory=dict)


def archive_html(source: str, route: str, html: str) -> str:
    """
    Gzip-archive a scraped page's raw HTML to data/raw/<source>/<route>/<timestamp>.html.gz.

    This is the highest-leverage fix in issue #17: it lets selectors be
    developed offline against real HTML (no re-scraping, no ban risk), gives
    the scrapers their first regression fixtures, and makes AI-fallback
    behavior replayable instead of dependent on live-site luck.
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = pathlib.Path("data") / "raw" / source / route / f"{ts}.html.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(html)
    return str(path)


class BaseScraper(abc.ABC):
    """
    Abstract base for all VegaBytes scrapers.

    To add a new data source:
      1. Create src/scrapers/<source_name>.py
      2. Subclass BaseScraper
      3. Implement scrape_route()
      4. Register in ScraperFactory below

    No changes to pipeline, DB, or dashboard required.
    """

    SOURCE_ID: str = ""  # Override in subclass e.g. "indigo_direct"
    REQUEST_DELAY: float = 30.0  # seconds between requests — polite scraping

    # ── Selector configuration ────────────────────────────────────────────
    # The ONE place a human edits after inspecting the live DOM (see the
    # capture checklist in docs/). Keys:
    #   card         — selector matching one fare card / result row (required)
    #   total_fare   — selector, relative to a card, for the total price text
    #   flight_number— optional selector, relative to a card
    #   airline      — optional selector, relative to a card (OTAs only, where
    #                  each row is a different carrier). Direct sites leave this
    #                  unset and rely on AIRLINE below.
    # Placeholders below match no real site on purpose — every scrape falls
    # through to the AI parser until these are replaced with real classes.
    SELECTORS: dict[str, str] = {}

    # Default carrier for a single-airline (direct) source. None for an OTA,
    # where the airline is read per-card from SELECTORS["airline"].
    AIRLINE: str | None = None

    # Container the AI fallback reads its HTML fragment from when selectors break.
    AI_FALLBACK_SELECTOR: str = "main"

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy
        self.log = structlog.get_logger(source=self.SOURCE_ID)

    # ── Extraction (browser-independent, unit-testable) ───────────────────
    @staticmethod
    def _parse_price(text: str) -> float:
        """Pull a rupee amount out of free text: '₹ 4,789' -> 4789.0."""
        cleaned = text.replace(" ", " ")
        match = re.search(r"[\d][\d,]*(?:\.\d+)?", cleaned)
        if not match:
            raise ValueError(f"no numeric price in {text!r}")
        return float(match.group(0).replace(",", ""))

    def extract_fares_from_html(
        self,
        html: str,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str = "economy",
        source_url: str | None = None,
    ) -> list[FareRecord]:
        """
        Extract fares from a page's HTML string using ``SELECTORS``.

        Operates on an HTML string (not a live Playwright page) so it can be
        developed and regression-tested offline against the archives written
        by ``archive_html()`` — no browser, no network, no ban risk.

        Raises SelectorExtractionError when the card selector matches nothing
        or no card yields a parseable fare, so the caller can fall back to the
        AI DOM parser on genuine breakage rather than on every request.
        """
        card_selector = self.SELECTORS.get("card")
        total_selector = self.SELECTORS.get("total_fare")
        if not card_selector or not total_selector:
            raise SelectorExtractionError(
                f"{self.SOURCE_ID}: SELECTORS missing 'card'/'total_fare' — not configured yet"
            )

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(card_selector)
        if not cards:
            raise SelectorExtractionError(
                f"{self.SOURCE_ID}: card selector {card_selector!r} matched 0 elements"
            )

        flight_selector = self.SELECTORS.get("flight_number")
        airline_selector = self.SELECTORS.get("airline")
        records: list[FareRecord] = []
        for card in cards:
            try:
                total_el = card.select_one(total_selector)
                if total_el is None:
                    continue
                total_fare = self._parse_price(total_el.get_text())

                flight_number = None
                if flight_selector:
                    el = card.select_one(flight_selector)
                    flight_number = el.get_text(strip=True) if el else None

                airline = self.AIRLINE or "Unknown"
                if airline_selector:
                    el = card.select_one(airline_selector)
                    if el and el.get_text(strip=True):
                        airline = el.get_text(strip=True)

                records.append(
                    FareRecord(
                        route=f"{origin}-{destination}",
                        airline=airline,
                        flight_number=flight_number,
                        cabin_class=cabin_class,
                        departure_date=departure_date,
                        booking_window=booking_window,
                        base_fare=None,  # populated by the tax-separation ETL (issue #5)
                        fuel_surcharge=None,
                        udf=None,
                        psf=None,
                        gst=None,
                        total_fare=total_fare,
                        source=self.SOURCE_ID,
                        source_url=source_url,
                    )
                )
            except (ValueError, AttributeError) as e:
                self.log.warning("selector_parse_error", error=str(e))

        if not records:
            raise SelectorExtractionError(
                f"{self.SOURCE_ID}: {len(cards)} card(s) matched but none yielded a parseable fare"
            )
        return records

    def _ai_fallback(
        self,
        page,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str,
    ) -> list[FareRecord]:
        """Run the AI DOM parser over the fallback container's HTML fragment."""
        # Lazy import — ai_dom_parser imports FareRecord from this module, so a
        # top-level import here would be circular.
        from .ai_dom_parser import AIdomParser

        try:
            html_fragment = page.inner_html(self.AI_FALLBACK_SELECTOR, timeout=5000)
        except Exception:
            html_fragment = page.evaluate("document.body.innerHTML")
        return AIdomParser().parse(
            html_fragment=html_fragment,
            context={
                "source": self.SOURCE_ID,
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "booking_window": booking_window,
                "cabin_class": cabin_class,
                "airline": self.AIRLINE,
            },
        )

    def _fetch_and_extract(
        self,
        url: str,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str,
        wait_timeout: int = 30_000,
    ) -> list[FareRecord]:
        """
        Shared Playwright fetch → archive → selector-extract → AI-fallback flow.

        Every source uses this identical pipeline, differing only in URL, date
        format, SELECTORS, AIRLINE, and AI_FALLBACK_SELECTOR — so the browser
        plumbing lives here once instead of copy-pasted three times.
        """
        # Imported lazily so extract_fares_from_html() (and its offline tests)
        # never need Playwright installed.
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        self.log.info("scraping", url=url)
        records: list[FareRecord] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                proxy={"server": self.proxy} if self.proxy else None,
            )
            try:
                context = browser.new_context(user_agent=DESKTOP_USER_AGENT)
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                page.goto(url, timeout=60_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=wait_timeout)
                except Exception:
                    pass

                html = page.content()
                raw_html_path = None
                try:
                    raw_html_path = archive_html(self.SOURCE_ID, f"{origin}-{destination}", html)
                except Exception as e:
                    self.log.warning("html_archive_failed", error=str(e))

                try:
                    records = self.extract_fares_from_html(
                        html,
                        origin,
                        destination,
                        departure_date,
                        booking_window,
                        cabin_class,
                        source_url=page.url,
                    )
                except SelectorExtractionError as e:
                    self.log.warning(
                        "css_selectors_failed", error=str(e), falling_back_to="ai_dom_parser"
                    )
                    records = self._ai_fallback(
                        page, origin, destination, departure_date, booking_window, cabin_class
                    )

                for r in records:
                    r.raw_html_path = raw_html_path
            finally:
                # try/finally so a Chromium process is never leaked on error
                # (previously a mid-scrape exception left one per tenacity retry).
                browser.close()
        self._sleep()
        return records

    @abc.abstractmethod
    def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        booking_window: int,
        cabin_class: str = "economy",
    ) -> list[FareRecord]:
        """
        Scrape fares for a specific route and date.
        Returns list of FareRecord (can be empty if no flights found).
        """
        ...

    def _sleep(self) -> None:
        """Polite delay between requests."""
        self.log.debug("rate_limiting", delay=self.REQUEST_DELAY)
        time.sleep(self.REQUEST_DELAY)


class ScraperFactory:
    """
    Registry of all available scrapers.
    Plug in a new source by adding one line to _registry.
    """

    _registry: dict[str, type[BaseScraper]] = {}

    @classmethod
    def register(cls, scraper_cls: type[BaseScraper]) -> type[BaseScraper]:
        """Decorator to register a scraper."""
        cls._registry[scraper_cls.SOURCE_ID] = scraper_cls
        return scraper_cls

    @classmethod
    def get(cls, source_id: str, proxy: str | None = None) -> BaseScraper:
        if source_id not in cls._registry:
            raise ValueError(
                f"Unknown scraper source: {source_id!r}. Available: {list(cls._registry)}"
            )
        return cls._registry[source_id](proxy=proxy)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._registry.keys())
