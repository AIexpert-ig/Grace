"""OpenAI service for Grace's neural core using OpenRouter Free Models."""
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize the Client pointing to OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENAI_API_KEY,
)

class OpenAIService:
    async def get_concierge_response(self, user_message: str) -> str:
        """Generate a luxury concierge response using a free high-end model via OpenRouter."""
        try:
            response = await client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are Grace, a world-class AI concierge for an ultra-luxury hotel. "
                            "Your tone is sophisticated, warm, and highly professional. "
                            "Keep responses concise but high-end. "
                            "If asked about rates, suggest they use the /rates command."
                        )
                    },
                    {"role": "user", "content": user_message}
                ],
                extra_headers={
                    "HTTP-Referer": "https://railway.app",
                    "X-Title": "Grace AI Concierge",
                },
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter Connection Error: {str(e)}")
            return (
                "I apologize, I am currently attending to another guest's request. "
                "May I assist you with our /rates or something else in the meantime?"
            )
