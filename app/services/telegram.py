"""Telegram service for sending alerts and processing bot messages."""
import logging
from typing import Any

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:  # pylint: disable=too-few-public-methods
    """Service for sending alerts and replying to users via Telegram."""

    async def process_update(self, update: dict[str, Any]) -> None:
        """Process a Telegram webhook update payload and reply to the user."""
        update_id = update.get("update_id")
        logger.info("Received Telegram update", extra={"update_id": update_id})

        # 1. Check if the update contains a standard text message
        if "message" in update and "text" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            user_text = update["message"]["text"]
            
            # Log the incoming message
            logger.info("Processing message", extra={"chat_id": chat_id, "text": user_text})

            # 2. Formulate Grace's response
            if user_text.startswith("/start"):
                reply_text = "Hello! I am Grace, your AI concierge. How can I assist you with your stay today?"
            else:
                reply_text = f"Grace is processing your request: '{user_text}' (AI integration pending)"

            # 3. Send the response back to the user
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        url,
                        json={"chat_id": chat_id, "text": reply_text}
                    )
                    response.raise_for_status()
                    logger.info("Reply sent successfully", extra={"chat_id": chat_id})
            except httpx.HTTPError as e:
                logger.error("Failed to send Telegram reply", extra={"error": str(e)}, exc_info=True)
            except Exception as e:
                logger.error("Unexpected error sending Telegram reply", extra={"error": str(e)}, exc_info=True)


    async def send_alert(self, message: str):
        """Send an admin alert message via Telegram.
        
        Args:
            message: The message to send to the admin chat.
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