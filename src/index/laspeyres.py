"""
Modified Laspeyres Airfare Price Index (APIx) Calculator.

Formula:
    APIx_t = Σ(P_it * Q_i0) / Σ(P_i0 * Q_i0) × 100

Where:
    P_it  = Current period base fare for route i
    P_i0  = Base period base fare for route i
    Q_i0  = DGCA passenger traffic weight for route i (base period)

Notes:
    - Uses base fare only (excl. taxes) to isolate pure price signal
    - Missing data handled via Carry-Forward Imputation
    - Seasonal routes tracked in separate sub-index, excluded from main APIx

Owner: Ankita
Related Issue: #2
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import structlog

log = structlog.get_logger()


@dataclass
class RouteWeight:
    """DGCA traffic-derived weight for a route."""

    route: str  # e.g. "DEL-BOM"
    weight: float  # normalised (all weights sum to 1.0)


@dataclass
class IndexResult:
    index_date: date
    apix_value: float
    base_period: date
    routes_included: int
    routes_missing: list[str]
    notes: str = ""


class LaspeyresIndexCalculator:
    """
    Computes the Modified Laspeyres Airfare Price Index.

    Usage:
        calculator = LaspeyresIndexCalculator(
            weights=dgca_weights,        # list[RouteWeight]
            base_period=date(2026, 8, 1) # first full month of data
        )
        result = calculator.compute(current_fares, current_date)
    """

    def __init__(self, weights: list[RouteWeight], base_period: date):
        self.weights = {w.route: w.weight for w in weights}
        self.base_period = base_period
        self._base_fares: dict[str, float] = {}  # populated from DB on first run

    def set_base_fares(self, fares: dict[str, float]) -> None:
        """Load base period fares from DB. Call once before computing."""
        self._base_fares = fares
        log.info("base_fares_loaded", routes=list(fares.keys()))

    def compute(
        self,
        current_fares: dict[str, float],  # {route: avg_base_fare}
        index_date: date,
    ) -> IndexResult:
        """
        Compute the APIx for a given date.

        current_fares: dict mapping route -> average base fare for that day
        """
        if not self._base_fares:
            raise RuntimeError("Base fares not loaded. Call set_base_fares() first.")

        numerator = 0.0
        denominator = 0.0
        routes_included = []
        routes_missing = []

        for route, weight in self.weights.items():
            base_fare = self._base_fares.get(route)
            current_fare = current_fares.get(route)

            if base_fare is None or base_fare <= 0:
                log.warning("missing_base_fare", route=route)
                routes_missing.append(route)
                continue

            if current_fare is None:
                # Carry-Forward Imputation: use base fare (index = 100 for this route).
                # Still counted in routes_included below, but flagged here so
                # callers (and the `notes` field) can see imputation happened.
                log.warning("missing_current_fare_carry_forward", route=route)
                current_fare = base_fare
                routes_missing.append(route)

            numerator += current_fare * weight
            denominator += base_fare * weight
            routes_included.append(route)

        if denominator == 0:
            raise ValueError("Denominator is zero — all routes missing base fares.")

        apix = (numerator / denominator) * 100.0

        log.info(
            "index_computed",
            date=str(index_date),
            apix=round(apix, 4),
            routes_included=len(routes_included),
            routes_missing=routes_missing,
        )

        return IndexResult(
            index_date=index_date,
            apix_value=round(apix, 4),
            base_period=self.base_period,
            routes_included=len(routes_included),
            routes_missing=routes_missing,
            notes=f"Carry-forward applied for: {routes_missing}" if routes_missing else "",
        )
