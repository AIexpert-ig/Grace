"""OpenAI service for Grace's neural core using OpenRouter."""
import json
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

    async def get_concierge_response(self, transcript: list) -> str:
        # Emergency check: If the key is missing, log it specifically
        if not self.api_key or self.api_key == "":
            logger.error("SYSTEM CRITICAL: OPENAI_API_KEY is empty in settings!")
            return "I am currently polishing the silver. How else may I assist you?"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Grace, the front desk AI concierge at the Courtyard by Marriott in Dubai.\n"
                    "CORE RULES:\n"
                    "1. You are talking on the phone. Keep responses conversational, warm, and very brief (1-2 sentences maximum).\n"
                    "2. NEVER use bullet points, numbered lists, or special formatting. Speak naturally.\n"
                    "3. If a guest asks for a 'reservation', ALWAYS assume they mean a hotel room stay, not a restaurant, unless they specify otherwise.\n"
                    "4. You work AT this specific hotel right now. You are part of the front desk team.\n"
                    "5. If you need to gather details (dates, number of people), ask for them ONE at a time. Do not overwhelm the guest with multiple questions.\n"
                    "6. If the user says goodbye or wants to end the call, say a polite sign-off and include the EXACT tag [HANGUP] at the very end of your response.\n"
                    "7. When you have collected the guest's Name, Check-In Date, Check-Out Date, and Room Type, you MUST use the book_room tool to finalize the reservation."
                )
            }
        ]

        for turn in transcript:
            role = "assistant" if turn.get("role") == "agent" else "user"
            messages.append({"role": role, "content": turn.get("content", "")})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "book_room",
                    "description": "Books a hotel room for a guest when all details are confirmed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guest_name": {"type": "string"},
                            "check_in": {"type": "string", "description": "e.g., Feb 22"},
                            "check_out": {"type": "string", "description": "e.g., Feb 27"},
                            "room_type": {"type": "string", "description": "e.g., Smoking, Non-smoking, Suite"}
                        },
                        "required": ["guest_name", "check_in", "check_out", "room_type"]
                    }
                }
            }
        ]

        try:
            response = await self.client.chat.completions.create(
                model="google/gemini-flash-1.5",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                if tool_call.function.name == "book_room":
                    args = json.loads(tool_call.function.arguments)
                    return {"type": "tool_call", "name": "book_room", "args": args}
            content = message.content or "I understand, how may I continue to assist you?"
            return {"type": "text", "content": content}
        except Exception as e:
            logger.error(f"OpenRouter Connection Error: {str(e)}")
            return {"type": "text", "content": "I apologize, I am currently attending to another guest. May I assist you with our /rates?"}
