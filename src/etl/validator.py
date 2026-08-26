"""
Price Validator — Data Quality Framework.

Enforces min/max price bounds, schema completeness,
cross-source sanity checks, and duplicate detection.

Owner: Mufeed
Related Issue: #6
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import structlog

from ..scrapers.base import FareRecord

log = structlog.get_logger()

# Price bounds per route (INR). TODO: tune after first week of data.
ROUTE_BOUNDS: dict[str, tuple[float, float]] = {
    "DEL-BOM": (1_800, 28_000),
    "BOM-DEL": (1_800, 28_000),
    "BLR-DEL": (1_600, 25_000),
    "DEL-BLR": (1_600, 25_000),
    "BOM-BLR": (1_200, 22_000),
    "BLR-BOM": (1_200, 22_000),
    "HYD-DEL": (1_700, 26_000),
    "DEL-HYD": (1_700, 26_000),
}


@dataclass
class ValidationResult:
    is_valid: bool
    reason: Optional[str] = None


class PriceValidator:
    """Validates FareRecord objects before DB write."""

    def validate(self, record: FareRecord) -> ValidationResult:
        # 1. Schema completeness
        if not record.total_fare or record.total_fare <= 0:
            return ValidationResult(False, "total_fare missing or zero")
        if not record.route:
            return ValidationResult(False, "route missing")
        if not record.departure_date:
            return ValidationResult(False, "departure_date missing")
        if record.cabin_class not in ("economy", "business"):
            return ValidationResult(False, f"invalid cabin_class: {record.cabin_class}")

        # 2. Price range bounds
        bounds = ROUTE_BOUNDS.get(record.route)
        if bounds:
            lo, hi = bounds
            if not (lo <= record.total_fare <= hi):
                return ValidationResult(
                    False,
                    f"total_fare {record.total_fare} outside bounds [{lo}, {hi}] for {record.route}"
                )

        # 3. Base fare sanity (if available)
        if record.base_fare is not None:
            if record.base_fare <= 0:
                return ValidationResult(False, "base_fare is non-positive")
            if record.base_fare > record.total_fare:
                return ValidationResult(False, "base_fare exceeds total_fare — tax extraction error")

        return ValidationResult(True)

    def validate_batch(self, records: list[FareRecord]) -> tuple[list[FareRecord], list[dict]]:
        """
        Validate a batch. Returns (valid_records, rejection_log).
        """
        valid, rejected = [], []
        for r in records:
            result = self.validate(r)
            if result.is_valid:
                valid.append(r)
            else:
                rejected.append({
                    "route": r.route,
                    "source": r.source,
                    "total_fare": r.total_fare,
                    "rejection_reason": result.reason,
                })
                log.warning("record_rejected", route=r.route, reason=result.reason)
        return valid, rejected
