import os
import json
import logging
from typing import Optional, Dict, Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Define Schema
class EscalationAnalysis(BaseModel):
    reasoning: str = Field(..., description="Brief analysis of why the guest is upset.")
    priority: str = Field(..., description="Escalation level: Low, Medium, or High.")
    sentiment: str = Field(..., description="Guest sentiment: Negative, Neutral, or Angry.")
    action_plan: str = Field(..., description="One sentence step to resolve the issue.")

# 2. Initialize Client
api_key = os.getenv("GEMINI_API_KEY")
client = None

if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize GenAI Client: {e}")
else:
    logger.warning("GEMINI_API_KEY is missing.")

async def _call_model(model_name: str, prompt: str) -> Optional[Dict[str, Any]]:
    """Helper function to call a specific model version."""
    logger.info(f"Attempting analysis with model: {model_name}")
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EscalationAnalysis,
        ),
    )
    if response.parsed:
        return response.parsed.model_dump()
    return json.loads(response.text)

# 3. Async Analysis Function with Fallback Strategy
async def analyze_escalation(guest_name: str, issue_text: str) -> Optional[Dict[str, Any]]:
    if not client:
        return None

    prompt = (
        f"Analyze the following hotel guest complaint from {guest_name}.\n\n"
        f"Complaint: {issue_text}\n\n"
        "Provide a structured analysis including priority and action plan."
    )

    try:
        # ATTEMPT 1: Try the latest model (Gemini 2.0 Flash)
        return await _call_model("gemini-2.0-flash", prompt)

    except Exception as e:
        # Check if it's a Rate Limit error (429) or Resource Exhausted
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            logger.warning(f"Gemini 2.0 rate limited. Falling back to Gemini 1.5 Flash...")
            try:
                # ATTEMPT 2: Fallback to the stable model (Gemini 1.5 Flash)
                return await _call_model("gemini-1.5-flash", prompt)
            except Exception as e2:
                logger.error(f"Fallback model also failed: {e2}")
        else:
            logger.error(f"Primary model failed with non-rate-limit error: {e}")

        # FINAL FALLBACK: Return safe default values
        return {
            "reasoning": "AI Service Busy. Automatic analysis skipped.",
            "priority": "Medium",
            "sentiment": "Neutral",
            "action_plan": "Please review this ticket manually."
        }
