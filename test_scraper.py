from datetime import date, timedelta
import time
import os
import structlog
import traceback
from dotenv import load_dotenv

from src.scrapers.base import ScraperFactory
# Ensure the modules are imported so they register in the factory
import src.scrapers.indigo_direct
import src.scrapers.airindia_direct
import src.scrapers.makemytrip

if __name__ == "__main__":
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    scrapers = ["indigo_direct", "airindia_direct", "makemytrip"]
    routes = [
        ("DEL", "BOM"),
        ("DEL", "BLR"),
        ("BOM", "BLR"),
        ("DEL", "CCU"),
        ("BLR", "HYD"),
        ("MAA", "DEL")
    ]
    
    target_date = date.today() + timedelta(days=7)
    
    # Load environment variables (including HTTP_PROXY if you have a rotating proxy)
    load_dotenv()
    proxy = os.getenv("HTTP_PROXY")
    if proxy:
        print(f"Using proxy: {proxy}")
    
    for source_id in scrapers:
        print(f"=== Initializing Scraper: {source_id} ===")
        try:
            scraper = ScraperFactory.get(source_id, proxy=proxy)
        except ValueError as e:
            print(f"Skipping {source_id}: {e}")
            continue

        for origin, destination in routes:
            print(f"[{source_id}] Scraping {origin}-{destination} for {target_date}...")
            try:
                # The scrapers have an internal REQUEST_DELAY, but we add an explicit
                # sleep in this test loop to be extra polite to the servers.
                results = scraper.scrape_route(origin, destination, target_date, 7)
                print(f"[{source_id}] Got {len(results)} records.")
                for r in results:
                    print(r)
            except Exception as e:
                if hasattr(e, "last_attempt"):
                    ex = e.last_attempt.exception()
                    print(f"[{source_id}] Failed with: {ex}")
                    traceback.print_exception(type(ex), ex, ex.__traceback__)
                else:
                    print(f"[{source_id}] Failed: {e}")
                    traceback.print_exc()
            
            print("Waiting 30 seconds before next request...")
            time.sleep(30)
