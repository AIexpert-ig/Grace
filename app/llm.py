import os
import logging
import asyncio

# Configure Logging
logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

# Global Client
model = None

def init_gemini():
    global model
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY is missing! The Brain is dead.")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("🧠 Gemini Brain Initialized Successfully.")
        return model
    except Exception as e:
        logger.error(f"❌ Failed to load Gemini Library: {e}")
        return None

# Initialize on load
init_gemini()

async def analyze_escalation(guest_name, text_input):
    global model
    if not model:
        # Try to revive the brain
        model = init_gemini()
        if not model:
            return {
                "priority": "Medium",
                "sentiment": "Neutral",
                "action_plan": "AI Offline (Check API Key)"
            }

    prompt = f"""
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
    
    try:
        # Run in a thread to avoid blocking
        response = await asyncio.to_thread(model.generate_content, prompt)
        import json
        clean_text = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_text)
    except Exception as e:
        logger.error(f"🧠 Brain Freeze: {e}")
        return {
            "priority": "Medium",
            "sentiment": "Neutral",
            "action_plan": "I heard you, but I am having trouble thinking right now."
        }
