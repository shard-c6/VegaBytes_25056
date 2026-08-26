"""
Telegram Alerting Bot — Pipeline monitoring.

Sends alerts when:
  - Scraper fails 3x consecutively for any route
  - No data received for 6+ hours
  - Price anomaly detected (outside expected bounds)
  - DB connection fails heartbeat check

Owner: Mukta
Related Issue: #8
"""
from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from typing import Optional

import structlog

log = structlog.get_logger()


class AlertLevel(Enum):
    INFO    = "ℹ️"
    WARNING = "⚠️"
    CRITICAL = "🚨"


class TelegramAlerter:
    """
    Sends structured alerts to a Telegram channel.

    Setup:
      1. Create bot via @BotFather → get TELEGRAM_BOT_TOKEN
      2. Add bot to your team channel → get TELEGRAM_CHAT_ID
      3. Set both in .env

    Usage:
        alerter = TelegramAlerter()
        alerter.send(AlertLevel.CRITICAL, "Scraper failed 3x", route="DEL-BOM", source="indigo")
    """

    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id   = os.getenv("TELEGRAM_CHAT_ID")
        self._enabled  = bool(self.bot_token and self.chat_id)
        if not self._enabled:
            log.warning("telegram_alerter_disabled", reason="TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")

    def send(self, level: AlertLevel, message: str, **context) -> bool:
        """Send a formatted alert to the Telegram channel."""
        if not self._enabled:
            log.info("alert_suppressed_no_config", message=message, level=level.name)
            return False

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        context_str = "\n".join(f"  • {k}: {v}" for k, v in context.items())
        text = (
            f"{level.value} *VegaBytes Pipeline Alert*\n"
            f"──────────────────────\n"
            f"*{message}*\n"
            f"{context_str}\n"
            f"──────────────────────\n"
            f"🕐 {timestamp}"
        )

        try:
            import httpx
            resp = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            resp.raise_for_status()
            log.info("alert_sent", level=level.name, message=message)
            return True
        except Exception as e:
            log.error("alert_failed", error=str(e))
            return False


class FailureTracker:
    """
    Tracks consecutive scraper failures per (source, route).
    Triggers alert after THRESHOLD consecutive failures.
    """

    THRESHOLD = 3

    def __init__(self, alerter: TelegramAlerter) -> None:
        self.alerter = alerter
        self._counts: dict[str, int] = {}

    def record_failure(self, source: str, route: str, error: str) -> None:
        key = f"{source}:{route}"
        self._counts[key] = self._counts.get(key, 0) + 1
        count = self._counts[key]
        log.warning("scraper_failure", source=source, route=route, consecutive=count, error=error)

        if count >= self.THRESHOLD:
            self.alerter.send(
                AlertLevel.CRITICAL,
                f"Scraper failed {count}x consecutively",
                source=source,
                route=route,
                error=error,
            )

    def record_success(self, source: str, route: str) -> None:
        key = f"{source}:{route}"
        if key in self._counts:
            del self._counts[key]
        log.info("scraper_success", source=source, route=route)
