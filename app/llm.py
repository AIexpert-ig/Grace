import os
import logging
import json
import google.generativeai as genai

logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

# 1. Setup the Key
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    logger.error("❌ GEMINI_API_KEY is NOT set in environment variables!")
else:
    # Log masked key to prove it is loaded (e.g. AIza...7890)
    masked = f"{API_KEY[:4]}...{API_KEY[-4:]}"
    logger.info(f"✅ Gemini Key Loaded: {masked}")
    genai.configure(api_key=API_KEY)

async def analyze_escalation(guest_name, issue):
    if not API_KEY:
        return {
            "priority": "High", 
            "sentiment": "Negative", 
            "action_plan": "System Error: GEMINI_API_KEY is missing."
        }

    try:
        # 2. Define the Model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
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
        
        logger.info(f"🧠 Asking Gemini about: {guest_name}...")
        
        # 3. Call Google
        response = model.generate_content(prompt)
        
        # 4. Clean the result (Gemini sometimes adds ```json ... ```)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        logger.info(f"📥 Gemini Answer: {clean_text[:50]}...")
        
        return json.loads(clean_text)

    except Exception as e:
        logger.error(f"🔥 AI CRASH: {e}")
        # Return the ACTUAL error to the frontend so we can see it
        return {
            "priority": "High",
            "sentiment": "Negative",
            "action_plan": f"AI Error: {str(e)}"
        }
