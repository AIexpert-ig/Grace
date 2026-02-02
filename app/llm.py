from google import genai
from google.genai import types
import os
import json
import logging

# Setup Logger
logger = logging.getLogger("app.llm")

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY")

async def analyze_escalation(guest_name, issue_text):
    """
    Analyzes the issue using the NEW Google GenAI SDK (v1.0+).
    """
    if not API_KEY:
        logger.error("❌ GEMINI_API_KEY is missing!")
        return {"action_plan": "Configuration Error - Missing API Key"}

    try:
        # Initialize the new Client
        client = genai.Client(api_key=API_KEY)

        prompt = f"""
        You are the Hotel Manager AI.
        Guest: {guest_name}
        Issue: {issue_text}
        
        Return specific JSON only (no markdown formatting):
        {{
            "priority": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
            "sentiment": "NEGATIVE" | "NEUTRAL" | "POSITIVE",
            "action_plan": "One short sentence for staff."
        }}
        """

        # Generate content using the new syntax
        # We use 'gemini-1.5-flash' which is standard on the new API
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json" 
            )
        )
        
        # The new SDK handles JSON parsing automatically if configured!
        # But we double-check just in case.
        try:
            return response.parsed
        except:
            return json.loads(response.text)

    except Exception as e:
        logger.error(f"❌ AI Analysis Failed (New SDK): {e}")
        return {
            "priority": "HIGH", 
            "sentiment": "NEGATIVE", 
            "action_plan": "AI Offline - Manual Escalation Required."
        }
