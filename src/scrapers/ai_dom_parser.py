"""
AI DOM Parser — Fallback when CSS selectors fail.

Uses Gemini Flash (free tier) to extract structured fare data
from raw HTML fragments. Triggered ONLY when primary CSS selectors
return empty/null — not used as primary to keep latency and cost minimal.

Owner: Shardul
Related Issue: #7
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from google import genai
import structlog

from .base import FareRecord

log = structlog.get_logger()

EXTRACTION_PROMPT = """
You are a precise data extraction assistant for an Indian government statistical project.

Extract ALL flight fare listings from the following HTML fragment.
Return a JSON array where each object has these exact keys:
  - "flight_number": string or null
  - "airline": string
  - "total_fare": number (in INR, digits only)
  - "base_fare": number or null (if shown separately)
  - "cabin_class": "economy" or "business"

Rules:
- Only extract non-stop direct flights
- Convert all amounts to INR (remove ₹, commas)
- If base fare is not shown, set to null
- If no fares found, return []
- Respond ONLY with valid JSON, no explanation

HTML:
{html}
"""


def _coerce_fare(value: Any, *, required: bool) -> Optional[float]:
    """
    Coerce a raw JSON fare value to float, rejecting shapes that would
    silently corrupt the index: bool (float(True) == 1.0 since bool is an
    int subtype) and non-finite floats (NaN/inf, which json.loads can't
    itself produce, but a model could emit as the bare token "NaN").
    """
    if value is None:
        if required:
            raise ValueError("required fare value missing")
        return None
    if isinstance(value, bool):
        raise ValueError(f"fare value must be numeric, got bool: {value!r}")
    fare = float(value)
    if not math.isfinite(fare):
        raise ValueError(f"fare value not finite: {fare!r}")
    return fare


@dataclass
class AIdomParser:
    """
    Gemini Flash-powered HTML fare extractor.

    Cost: ~0 (free tier: 15 RPM, 1M tokens/min for Gemini Flash)
    Latency: ~2-4 seconds per call (acceptable for fallback only)
    """

    model_name: str = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"

    def __post_init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set in environment")
        self._client = genai.Client(api_key=api_key)
        self.log = structlog.get_logger(parser="ai_dom_parser")

    def parse(self, html_fragment: str, context: dict[str, Any]) -> list[FareRecord]:
        """
        Parse fares from an HTML fragment using Gemini Flash.

        Args:
            html_fragment: The relevant section of the page HTML (NOT full page)
            context: Route/date/window metadata to enrich results

        Returns:
            List of FareRecord objects, empty if parsing fails
        """
        if not html_fragment or len(html_fragment) < 50:
            self.log.warning("html_fragment_too_short", length=len(html_fragment))
            return []

        # Truncate to avoid token limit (keep first 8000 chars — price section)
        truncated_html = html_fragment[:8000]

        prompt = EXTRACTION_PROMPT.format(html=truncated_html)
        try:
            response = self._client.models.generate_content(model=self.model_name, contents=prompt)
        except Exception as e:
            # Auth, quota, network, or transport failure — must be loud and
            # distinguishable from a parse failure, never a silent [].
            self.log.error("gemini_api_call_failed", error=str(e), error_type=type(e).__name__)
            return []

        response_text = response.text or ""
        try:
            raw_json = response_text.strip().removeprefix("```json").removesuffix("```").strip()
            extracted = json.loads(raw_json)
        except json.JSONDecodeError as e:
            self.log.error(
                "gemini_response_not_json", error=str(e), raw_response=response_text[:500]
            )
            return []

        if not isinstance(extracted, list) or not all(isinstance(item, dict) for item in extracted):
            # The prompt asks for a JSON array of objects, but nothing stops
            # the model from returning a bare object, string, or number.
            self.log.error("gemini_response_invalid_shape", raw_response=response_text[:500])
            return []
        self.log.info("ai_parse_success", fares_found=len(extracted))

        records = []
        for item in extracted:
            try:
                records.append(FareRecord(
                    route=f"{context['origin']}-{context['destination']}",
                    airline=item.get("airline") or context.get("airline") or "Unknown",
                    flight_number=item.get("flight_number"),
                    cabin_class=item.get("cabin_class") or context.get("cabin_class") or "economy",
                    departure_date=context["departure_date"],
                    booking_window=context["booking_window"],
                    base_fare=_coerce_fare(item.get("base_fare"), required=False),
                    fuel_surcharge=None,
                    udf=None,
                    psf=None,
                    gst=None,
                    total_fare=_coerce_fare(item.get("total_fare"), required=True),
                    source=f"ai_parser:{context['source']}",
                    source_url=None,
                ))
            except (KeyError, TypeError, ValueError) as e:
                # TypeError covers e.g. total_fare: null -> float(None); without
                # it one malformed record would abort the whole batch instead
                # of just being skipped.
                self.log.warning("record_parse_error", error=str(e), item=item)

        return records
