import os
import logging
import json
import google.generativeai as genai

logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

# 1. Setup the Key
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logger.error("❌ GEMINI_API_KEY is missing!")
else:
    genai.configure(api_key=API_KEY)

async def analyze_escalation(guest_name, issue):
    if not API_KEY:
        return {
            "priority": "High", 
            "sentiment": "Negative", 
            "action_plan": "System Error: GEMINI_API_KEY is missing."
        }

    try:
        # 2. Use the STABLE Model (gemini-pro)
        # This is the most reliable model for free-tier keys
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        You are a hotel manager.
        Guest: {guest_name}
        Issue: {issue}
        
        Return a valid JSON object (NO markdown, NO comments) with:
        {{
            "priority": "High/Medium/Low",
            "sentiment": "Negative/Neutral/Positive",
            "action_plan": "One specific, professional action to resolve this."
        }}
        """
        
        logger.info(f"🧠 Asking Gemini (Pro) about: {guest_name}...")
        
        response = model.generate_content(prompt)
        
        # 3. Clean the result
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        logger.info(f"📥 Gemini Answer: {clean_text[:50]}...")
        
        return json.loads(clean_text)

    except Exception as e:
        logger.error(f"🔥 AI CRASH: {e}")
        return {
            "priority": "High",
            "sentiment": "Negative",
            "action_plan": f"AI Error: {str(e)}"
        }
