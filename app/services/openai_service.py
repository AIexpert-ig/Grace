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
                    "You are Grace, the Master AI Concierge at the Courtyard by Marriott & Spa in Dubai.\n"
                    "CORE RULES:\n"
                    "1. Keep responses conversational, warm, and brief (1-2 sentences max).\n"
                    "2. NEVER use bullet points. Speak naturally.\n"
                    "3. You handle BOTH hotel room stays AND spa/salon appointments.\n"
                    "4. Ask for booking details ONE at a time. Do not overwhelm the guest.\n"
                    "5. If they want a room, collect: Name, Check-in, Check-out, and Room Type. Then use the book_room tool.\n"
                    "6. If they want a spa or salon service, collect: Name, Service Type, and Date/Time. Then use the book_appointment tool.\n"
                    "7. ENDING THE CALL: If the user says goodbye, append exactly [HANGUP] to the end of your response."
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
            },
            {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Books a spa or salon appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "client_name": {"type": "string"},
                            "service_type": {"type": "string", "description": "e.g., haircut, massage"},
                            "date_time": {"type": "string", "description": "e.g., Tomorrow at 2 PM"}
                        },
                        "required": ["client_name", "service_type", "date_time"]
                    }
                }
            }
        ]

        try:
            response = await self.client.chat.completions.create(
                model="arcee-ai/trinity-large-preview:free",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                fn_name = tool_call.function.name
                if fn_name in {"book_room", "book_appointment"}:
                    args = json.loads(tool_call.function.arguments)
                    return {"type": "tool_call", "name": fn_name, "args": args}
            content = message.content or "I understand, how may I continue to assist you?"
            return {"type": "text", "content": content}
        except Exception as e:
            logger.error(f"OpenRouter Connection Error: {str(e)}")
            # If the model rejected the tools parameter, retry without it
            if "tool" in str(e).lower() or "empty" in str(e).lower():
                try:
                    fallback = await self.client.chat.completions.create(
                        model="arcee-ai/trinity-large-preview:free",
                        messages=messages
                    )
                    content = fallback.choices[0].message.content or "I understand, how may I continue to assist you?"
                    return {"type": "text", "content": content}
                except Exception as e2:
                    logger.error(f"OpenRouter Fallback Error: {str(e2)}")
            return {"type": "text", "content": "I am experiencing a slight system delay on my end. Could you please repeat that?"}
