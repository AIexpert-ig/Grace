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

DEFAULT_MODEL_CANDIDATES = [
    "models/gemini-1.5-pro",
    "models/gemini-1.5-flash",
    "models/gemini-1.0-pro",
    "models/gemini-pro",
]

_RESOLVED_MODEL_NAME = None

def _resolve_model_name():
    global _RESOLVED_MODEL_NAME
    if _RESOLVED_MODEL_NAME:
        return _RESOLVED_MODEL_NAME

    env_model = os.getenv("GEMINI_MODEL")
    if env_model:
        _RESOLVED_MODEL_NAME = env_model
        logger.info("Using Gemini model from GEMINI_MODEL: %s", _RESOLVED_MODEL_NAME)
        return _RESOLVED_MODEL_NAME

    try:
        models = [
            m for m in genai.list_models()
            if "generateContent" in getattr(m, "supported_generation_methods", [])
        ]
        names = {m.name for m in models}
        for candidate in DEFAULT_MODEL_CANDIDATES:
            if candidate in names:
                _RESOLVED_MODEL_NAME = candidate
                break
        if not _RESOLVED_MODEL_NAME:
            for m in models:
                if "gemini" in m.name:
                    _RESOLVED_MODEL_NAME = m.name
                    break
        if not _RESOLVED_MODEL_NAME and models:
            _RESOLVED_MODEL_NAME = models[0].name
    except Exception as e:
        logger.warning("Model discovery failed: %s", e)

    if not _RESOLVED_MODEL_NAME:
        _RESOLVED_MODEL_NAME = "models/gemini-1.5-flash"

    logger.info("Using Gemini model: %s", _RESOLVED_MODEL_NAME)
    return _RESOLVED_MODEL_NAME

async def analyze_escalation(guest_name, issue):
    if not API_KEY:
        return {
            "priority": "High", 
            "sentiment": "Negative", 
            "action_plan": "System Error: GEMINI_API_KEY is missing."
        }

    try:
        # 2. Use a supported model. Prefer GEMINI_MODEL or auto-discover.
        model_name = _resolve_model_name()
        model = genai.GenerativeModel(model_name)
        
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
