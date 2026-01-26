# Ensure these are at the TOP of the file
from app.services.openai_service import OpenAIService
openai_service = OpenAIService()

# No code belongs here - remove this stray/incorrect block.
import logging
from typing import Any

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_db

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for sending alerts and replying to users via Telegram."""

    async def _send_message(self, chat_id: int, text_content: str) -> None:
        """Helper to send a message back to Telegram."""
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text_content, "parse_mode": "Markdown"}
                )
                response.raise_for_status()
                logger.info("Reply sent successfully", extra={"chat_id": chat_id})
        except Exception as e:
            logger.error("Failed to send Telegram reply", extra={"error": str(e)})

    async def process_update(self, update: dict[str, Any]) -> None:
        """Process a Telegram webhook update payload and reply to the user."""
        update_id = update.get("update_id")
        if "message" not in update or "text" not in update["message"]:
            return

        chat_id = update["message"]["chat"]["id"]
        user_text = update["message"]["text"]

        logger.info("Processing message", extra={"update_id": update_id, "chat_id": chat_id})

        # COMMAND: /start
        if user_text.startswith("/start"):
            reply = "🛎 *Welcome to Grace Luxury AI*\n\nI am your digital concierge. You can ask me about our current room /rates, or simply tell me how I can help you today."
            await self._send_message(chat_id, reply)

        # COMMAND: /rates
        elif user_text.startswith("/rates"):
            rates_text = await self._get_live_rates()
            await self._send_message(chat_id, rates_text)

        # ALL OTHER TEXT: AI Concierge Brain Placeholder
        else:
            ai_reply = f"✨ *Grace Concierge*:\n\nThank you for your request regarding '{user_text}'. I am currently being connected to my neural core. In the meantime, would you like to see our /rates?"
            await self._send_message(chat_id, ai_reply)

    async def _get_live_rates(self) -> str:
        """Fetch real rates from the PostgreSQL database."""
        try:
            async for db in get_db():
                # Attempt to query your database
                result = await db.execute(text("SELECT room_type, price FROM rates LIMIT 3"))
                rows = result.all()

                if not rows:
                    return "Our current seasonal rates start at *$199/night* for a Classic King Room. Please check back for live suite availability."

                msg = "🏨 *Current Room Rates:*\n\n"
                for row in rows:
                    msg += f"• {row[0]}: *${row[1]}/night*\n"
                msg += "\n_Would you like to proceed with a booking?_"
                return msg
        except Exception as exc:
            logger.error("Database error in rates: %s", exc)
            return "Our standard rooms currently start at *$199/night*. Contact our front desk for elite suite pricing."
        return "Our standard rooms currently start at *$199/night*. Contact our front desk for elite suite pricing."

    async def send_alert(self, message: str) -> None:
        """Send an admin alert message via Telegram."""
        await self._send_message(int(settings.TELEGRAM_CHAT_ID), f"🚨 *SYSTEM ALERT*\n{message}")
