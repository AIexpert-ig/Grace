"""OpenAI service for Grace's neural core."""
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI Client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class OpenAIService:
    async def get_concierge_response(self, user_message: str) -> str:
        """Generate a luxury concierge response using GPT-4."""
        try:
            response = await client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are Grace, a world-class AI concierge for an ultra-luxury hotel. "
                            "Your tone is sophisticated, warm, and highly professional. "
                            "You anticipate needs and speak with elegance. Keep responses concise "
                            "but high-end. If asked about rates, suggest they use the /rates command."
                        )
                    },
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Core Error: {e}")
            return "I apologize, but I am having a moment of reflection. How else may I assist you?"