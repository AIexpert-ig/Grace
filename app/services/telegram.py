"""Telegram service for sending alerts."""
import logging
from typing import Any

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:  # pylint: disable=too-few-public-methods
    """Service for sending alerts via Telegram."""

    async def process_update(self, update: dict[str, Any]) -> None:
        """Process a Telegram webhook update payload."""
        update_id = update.get("update_id")
        logger.info("Received Telegram update", extra={"update_id": update_id})

    async def send_alert(self, message: str):
        """Send an alert message via Telegram.
        
        Args:
            message: The message to send.
        """
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": message}
                )
                response.raise_for_status()
                logger.info("Telegram alert sent successfully", extra={"message_length": len(message)})
        except httpx.HTTPError as e:
            logger.error("Failed to send Telegram alert", extra={"error": str(e)}, exc_info=True)
            # Don't raise - alert failures shouldn't break the webhook processing
        except Exception as e:
            logger.error("Unexpected error sending Telegram alert", extra={"error": str(e)}, exc_info=True)
