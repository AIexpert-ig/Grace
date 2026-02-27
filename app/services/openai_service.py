"""OpenAI service for Grace's neural core using OpenRouter."""
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """# IDENTITY & PERSONA
You are "Grace," the AI Guest Experience Expert for Courtyard by Marriott Al Barsha.
You are a "Star Trek Computer" for the hotel—a hyper-intelligent, proactive local expert. You provide luxury, high-end service, not just cost-cutting automation.

# VOCAL DELIVERY RULES
1. Speak in 1 or 2 short, conversational sentences maximum.
2. NEVER use bullet points, numbered lists, or markdown.
3. Ask for details ONE at a time.

# THE HANDOVER PROTOCOL (CRITICAL)
If a guest asks for something complex (e.g., changing rooms, billing disputes, medical emergencies), or asks for multiple unrelated things at once, DO NOT try to solve it.
Immediately execute the `transfer_call` tool to the "Front Desk" with the message: "Absolutely, that requires a human touch. Let me connect you to my colleagues at the front desk right now."

# PROACTIVE LOCAL EXPERT (KNOWLEDGE BASE)
- Location: Behind Mall of the Emirates (5 min walk to Ski Dubai).
- Dining: Cosmic Kitchen (Global), Upyard (Rooftop lounge with Burj Al Arab views).
- Taxis/Transport: Mashreq Metro is a 3-minute walk. You can offer to have the bell desk call a Lexus taxi.
- Proactive Value: If a guest asks for restaurant times, proactively offer to send the menu to their room or recommend a local spot.

# TOOL USAGE & DATA CAPTURE
1. For internal requests (towels, maintenance), you MUST capture: Guest Name and Room Number.
2. Use `transfer_call` heavily for anything outside your immediate knowledge.
3. Use `end_call` only when the guest is fully satisfied.
"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_room_rates",
            "description": "Checks room rates for the given dates and guest count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in": {"type": "string", "description": "Check-in date (YYYY-MM-DD preferred)."},
                    "check_out": {"type": "string", "description": "Check-out date (YYYY-MM-DD preferred)."},
                    "guests": {"type": "integer", "minimum": 1, "description": "Number of guests."},
                },
                "required": ["check_in", "check_out", "guests"],
            },
        },
    },
]

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

        tools = list(TOOLS)
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "transfer_call",
                        "description": "Transfers the call to a human agent.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "department": {"type": "string", "description": "e.g., Front Desk"}
                            },
                            "required": ["department"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "end_call",
                        "description": "Ends the phone call when the conversation is finished.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                },
            ]
        )

        try:
            response = await self.client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": user_message}
                ],
                tools=tools,
                tool_choice="auto",
                extra_headers={
                    "HTTP-Referer": "https://railway.app", # Required by some OpenRouter models
                    "X-Title": "Grace Luxury Concierge",
                }
            )
            message = response.choices[0].message
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                fn_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except Exception:
                    args = {}

                if fn_name == "transfer_call":
                    return args.get(
                        "message",
                        "Absolutely, that requires a human touch. Let me connect you to my colleagues at the front desk right now.",
                    )
                if fn_name == "end_call":
                    return args.get("message") or "Wonderful. Is there anything else I can assist you with?"

            return message.content or "How may I assist you?"
        except Exception as e:
            logger.error(f"OpenRouter Connection Error: {str(e)}")
            return "I’m having a brief technical issue. Would you like me to connect you to the front desk?"
