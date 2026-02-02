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

# 1. Define the Strict Output Schema using Pydantic
class EscalationAnalysis(BaseModel):
    reasoning: str = Field(..., description="Brief analysis of why the guest is upset.")
    priority: str = Field(..., description="Escalation level: Low, Medium, or High.")
    sentiment: str = Field(..., description="Guest sentiment: Negative, Neutral, or Angry.")
    action_plan: str = Field(..., description="One sentence step to resolve the issue.")

# 2. Initialize the new Client
# Ensure GEMINI_API_KEY is set in your Railway variables
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.warning("GEMINI_API_KEY is missing. AI features will fail.")

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    logger.error(f"Failed to initialize GenAI Client: {e}")
    client = None

def analyze_escalation(guest_name: str, issue_text: str) -> Optional[Dict[str, Any]]:
    """
    Analyzes a hotel guest complaint using Gemini 2.0 Flash and returns a structured dictionary.
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
        # 3. Call the model with Structured Output Config
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EscalationAnalysis, # Pass the Pydantic class directly
            ),
        )

        # 4. Parse the response
        # The new SDK parses JSON automatically into the Pydantic object if schema is provided
        if response.parsed:
             # Convert Pydantic object back to a standard Python dict for FastAPI
            return response.parsed.model_dump()
        
        # Fallback if parsing didn't occur automatically (rare with strict schema)
        raw_text = response.text
        return json.loads(raw_text)

    except Exception as e:
        logger.error(f"Error analyzing escalation: {e}")
        # Return a safe fallback or None so your server doesn't crash
        return {
            "reasoning": "Error analyzing input.",
            "priority": "Unknown",
            "sentiment": "Unknown",
            "action_plan": "Please review manually."
        }
