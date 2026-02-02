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

# 3. Async Analysis Function
async def analyze_escalation(guest_name: str, issue_text: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes a guest complaint using Gemini 2.0 Flash (Async).
    """
    if not client:
        logger.error("Client not initialized.")
        return None

    prompt = (
        f"Analyze the following hotel guest complaint from {guest_name}.\n\n"
        f"Complaint: {issue_text}\n\n"
        "Provide a structured analysis including priority and action plan."
    )

    try:
        # NOTICE: We use 'client.aio' for asynchronous execution
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EscalationAnalysis,
            ),
        )

        # Parse valid response
        if response.parsed:
            return response.parsed.model_dump()
        
        return json.loads(response.text)

    except Exception as e:
        # Logs the 429 or 500 error from Google without crashing your app
        logger.error(f"AI Analysis Failed: {e}")
        
        # Return a safe fallback so your frontend doesn't break
        return {
            "reasoning": "AI Service Temporarily Unavailable (Rate Limit Reached).",
            "priority": "Medium",
            "sentiment": "Neutral",
            "action_plan": "Please review this ticket manually."
        }
