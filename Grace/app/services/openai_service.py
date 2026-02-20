"""OpenAI service for Grace's neural core using OpenRouter."""
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        # We define the client inside __init__ to ensure it pulls 
        # the LATEST settings from Railway variables.
        self.api_key = settings.OPENAI_API_KEY
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    async def get_concierge_response(self, user_message: str) -> str:
        # Emergency check: If the key is missing, log it specifically
        if not self.api_key or self.api_key == "":
            logger.error("SYSTEM CRITICAL: OPENAI_API_KEY is empty in settings!")
            return "I am currently polishing the silver. How else may I assist you?"

        try:
            response = await self.client.chat.completions.create(
                model="google/gemini-2.0-pro-exp-02-05:free",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are Grace, a world-class AI concierge. Your tone is elegant, warm, and professional."
                    },
                    {"role": "user", "content": user_message}
                ],
                extra_headers={
                    "HTTP-Referer": "https://railway.app", # Required by some OpenRouter models
                    "X-Title": "Grace Luxury Concierge",
                }
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter Connection Error: {str(e)}")
            return "I apologize, I am currently attending to another guest. May I assist you with our /rates?"
