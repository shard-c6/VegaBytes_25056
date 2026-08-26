"""
Base scraper interface — factory pattern.
All source-specific scrapers must inherit from BaseScraper.

Owner: Shardul (Issue #7 — AI DOM Parser, Issue #4 — Demo Strategy)
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import structlog

log = structlog.get_logger()


@dataclass
class FareRecord:
    """Structured fare record matching the DB schema."""
    route: str                  # e.g. "DEL-BOM"
    airline: str
    flight_number: Optional[str]
    cabin_class: str            # "economy" | "business"
    departure_date: date
    booking_window: int         # days ahead: 1, 7, 30
    base_fare: Optional[float]
    fuel_surcharge: Optional[float]
    udf: Optional[float]
    psf: Optional[float]
    gst: Optional[float]
    total_fare: float
    source: str                 # scraper identifier
    source_url: Optional[str]
    extra: dict = field(default_factory=dict)


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

    SOURCE_ID: str = ""          # Override in subclass e.g. "indigo_direct"
    REQUEST_DELAY: float = 30.0  # seconds between requests — polite scraping

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.log = structlog.get_logger(source=self.SOURCE_ID)

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
    def get(cls, source_id: str, proxy: Optional[str] = None) -> BaseScraper:
        if source_id not in cls._registry:
            raise ValueError(f"Unknown scraper source: {source_id!r}. Available: {list(cls._registry)}")
        return cls._registry[source_id](proxy=proxy)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._registry.keys())
