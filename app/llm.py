import google.generativeai as genai
import os
import json
import logging

# Setup Logger
logger = logging.getLogger("app.llm")

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# 🧠 CONFIGURATION: Use the Stable Model
# We use 'gemini-pro' because it is 100% available and stable.
model = genai.GenerativeModel('gemini-pro')

async def analyze_escalation(guest_name, issue_text):
    """
    Analyzes the guest issue using Google Gemini AI.
    Returns a dictionary with priority, sentiment, and action plan.
    """
    
    prompt = f"""
    You are the Hotel Manager AI for a luxury hotel.
    Analyze this guest complaint:
    
    Guest: {guest_name}
    Issue: {issue_text}
    
    Return a JSON object with these 3 fields:
    1. "priority": "CRITICAL", "HIGH", "MEDIUM", or "LOW"
    2. "sentiment": "ANGRY", "DISAPPOINTED", "NEUTRAL", or "HAPPY"
    3. "action_plan": A one-sentence instruction for staff.
    
    IMPORTANT: Return ONLY the JSON. No Markdown formatting.
    """

    try:
        response = model.generate_content(prompt)
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
        
    except Exception as e:
        logger.error(f"❌ AI Analysis Failed: {e}")
        # Fail gracefully so the server doesn't crash
        return {
            "priority": "HIGH", 
            "sentiment": "NEGATIVE", 
            "action_plan": "AI Offline - Manager attention required immediately."
        }
