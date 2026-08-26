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
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import google.generativeai as genai
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


@dataclass
class AIdomParser:
    """
    Gemini Flash-powered HTML fare extractor.

    Cost: ~0 (free tier: 15 RPM, 1M tokens/min for Gemini Flash)
    Latency: ~2-4 seconds per call (acceptable for fallback only)
    """

    model_name: str = "gemini-1.5-flash"

    def __post_init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set in environment")
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.model_name)
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

        try:
            prompt = EXTRACTION_PROMPT.format(html=truncated_html)
            response = self._model.generate_content(prompt)
            raw_json = response.text.strip().lstrip("```json").rstrip("```").strip()
            extracted: list[dict] = json.loads(raw_json)
            self.log.info("ai_parse_success", fares_found=len(extracted))
        except (json.JSONDecodeError, Exception) as e:
            self.log.error("ai_parse_failed", error=str(e))
            return []

        records = []
        for item in extracted:
            try:
                records.append(FareRecord(
                    route=f"{context['origin']}-{context['destination']}",
                    airline=item.get("airline", context.get("airline", "Unknown")),
                    flight_number=item.get("flight_number"),
                    cabin_class=item.get("cabin_class", context.get("cabin_class", "economy")),
                    departure_date=context["departure_date"],
                    booking_window=context["booking_window"],
                    base_fare=item.get("base_fare"),
                    fuel_surcharge=None,
                    udf=None,
                    psf=None,
                    gst=None,
                    total_fare=float(item["total_fare"]),
                    source=f"ai_parser:{context['source']}",
                    source_url=None,
                ))
            except (KeyError, ValueError) as e:
                self.log.warning("record_parse_error", error=str(e), item=item)

        return records
