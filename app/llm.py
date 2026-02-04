import os
import logging
import asyncio
import google.generativeai as genai

# Configure Logging
logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

# Global Client
model = None

def get_best_available_model():
    """
    ZERO BULLSHIT MODE:
    Don't guess the name. Ask the API what is available.
    """
    try:
        logger.info("🔍 Scanning for available models...")
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        logger.info(f"📋 Found Models: {available_models}")

        # Priority List (Newest to Oldest) - Adapts to 2026
        priority_list = [
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
            "models/gemini-pro",
        ]

        # 1. Try to match a preferred model
        for preferred in priority_list:
            if preferred in available_models:
                logger.info(f"✅ Selected Preferred Model: {preferred}")
                return genai.GenerativeModel(preferred)

        # 2. If no preferred match, just grab the first valid one
        if available_models:
            first_choice = available_models[0]
            logger.warning(f"⚠️ Preferred models missing. Using fallback: {first_choice}")
            return genai.GenerativeModel(first_choice)

        logger.error("❌ No models found that support 'generateContent'. API Key might be invalid or has no access.")
        return None

    except Exception as e:
        logger.error(f"❌ Failed to list models: {e}")
        return None

def init_gemini():
    global model
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY is missing!")
        return None

    try:
        genai.configure(api_key=api_key)
        model = get_best_available_model()
        if model:
             logger.info("🧠 Gemini Brain Initialized Successfully.")
        return model
    except Exception as e:
        logger.error(f"❌ Critical Brain Failure: {e}")
        return None

# Initialize on load
init_gemini()

async def analyze_escalation(guest_name, text_input):
    global model
    if not model:
        model = init_gemini()
        if not model:
            return {
                "priority": "Medium",
                "sentiment": "Neutral",
                "action_plan": "AI Offline (No Valid Model Found)"
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
