"""
Central config: the route basket and advance-purchase windows.

Single source of truth so the scraper (what to collect), the DB seed (which
routes the database will accept — unknown routes are skipped, see
db.insert_scraped_fares) and the index never drift apart.

Both follow SIH PS 26056:
  • a basket of representative DGCA city-pairs
  • advance-purchase windows T+1, T+7, T+15, T+30, T+45
"""

from __future__ import annotations

# Representative city-pairs from the problem statement (chosen on DGCA
# passenger-traffic basis). Keep in IATA origin→destination order.
ROUTES: list[tuple[str, str]] = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL"),
]

# Advance-purchase windows in days ahead of departure (PS: T+1/7/15/30/45).
BOOKING_WINDOWS: list[int] = [1, 7, 15, 30, 45]
