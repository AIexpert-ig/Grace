import os
import logging
import asyncio
import json

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

MODEL_PRIMARY = "models/gemini-1.5-flash"
MODEL_FALLBACK = "models/gemini-pro"

HARD_CODED_RESPONSE = {
    "priority": "Medium",
    "sentiment": "Neutral",
    "action_plan": "We will acknowledge the guest and dispatch a staff member immediately."
}


def _configure_client() -> bool:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is missing")
        return False
    genai.configure(api_key=api_key)
    return True


def _build_prompt(guest_name: str, text_input: str) -> str:
    return f"""
    You are Grace, a hotel manager.
    Guest: {guest_name}
    Message: "{text_input}"

    Output JSON only:
    {{
        "priority": "High/Medium/Low",
        "sentiment": "Positive/Neutral/Negative",
        "action_plan": "A short, professional sentence saying exactly what you will do."
    }}
    """


def _parse_json_response(text: str) -> dict:
    clean_text = text.strip().replace("```json", "").replace("```", "")
    return json.loads(clean_text)


async def _generate_with_model(model_name: str, prompt: str):
    model = genai.GenerativeModel(model_name)
    return await asyncio.to_thread(model.generate_content, prompt)


async def analyze_escalation(guest_name, text_input):
    if not _configure_client():
        return HARD_CODED_RESPONSE

    prompt = _build_prompt(guest_name, text_input)

    try:
        response = await _generate_with_model(MODEL_PRIMARY, prompt)
        return _parse_json_response(response.text)
    except ResourceExhausted as e:
        logger.warning("Primary model quota exhausted, falling back to %s: %s", MODEL_FALLBACK, e)
        try:
            response = await _generate_with_model(MODEL_FALLBACK, prompt)
            return _parse_json_response(response.text)
        except Exception as fallback_error:
            logger.error("Fallback model failed: %s", fallback_error)
            return HARD_CODED_RESPONSE
    except Exception as e:
        logger.error("Primary model failed: %s", e)
        return HARD_CODED_RESPONSE
