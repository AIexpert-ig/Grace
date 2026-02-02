import google.generativeai as genai
import os
import json
import logging

# Setup Logger
logger = logging.getLogger("app.llm")

# Configure API Key
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

async def analyze_escalation(guest_name, issue_text):
    """
    Analyzes the issue using the first working Gemini model found.
    """
    
    # 🧠 THE SKELETON KEY: Try these models in order
    model_options = [
        'gemini-1.5-flash',       # The new standard
        'gemini-1.5-flash-latest', # The bleeding edge
        'gemini-1.0-pro',         # The reliable classic
        'gemini-pro'              # The old name
    ]

    prompt = f"""
    You are the Hotel Manager AI.
    Guest: {guest_name}
    Issue: {issue_text}
    
    Return specific JSON only:
    {{
        "priority": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
        "sentiment": "NEGATIVE" | "NEUTRAL" | "POSITIVE",
        "action_plan": "One short sentence for staff."
    }}
    """

    for model_name in model_options:
        try:
            # Try to load the model
            model = genai.GenerativeModel(model_name)
            
            # Try to generate content
            response = model.generate_content(prompt)
            
            # If we get here, it worked! Clean and return.
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
            
        except Exception as e:
            # If this model fails, log it and try the next one
            logger.warning(f"⚠️ Model '{model_name}' failed: {e}")
            continue

    # If ALL fail:
    logger.error("❌ All AI models failed.")
    return {
        "priority": "HIGH", 
        "sentiment": "NEGATIVE", 
        "action_plan": "AI Offline - Manual Escalation Required."
    }
