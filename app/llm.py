import os
import logging
import asyncio
import json
import google.generativeai as genai  # pylint: disable=import-error

# --- LOGGING ---
logger = logging.getLogger("app.llm")
logger.setLevel(logging.INFO)

# --- CONFIGURATION ---
# Based on your logs, these are the models you actually have access to.
PRIMARY_MODEL = "models/gemini-flash-latest"   # Fast, usually free
BACKUP_MODEL  = "models/gemini-pro-latest"     # Reliable backup

model_primary = None
model_backup = None

def init_gemini():
    global model_primary, model_backup
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("❌ GEMINI_API_KEY is missing.")
        return None

    try:
        genai.configure(api_key=api_key)
        model_primary = genai.GenerativeModel(PRIMARY_MODEL)
        model_backup = genai.GenerativeModel(BACKUP_MODEL)
        logger.info(f"🧠 Brain Online: {PRIMARY_MODEL} (Backup: {BACKUP_MODEL})")
        return model_primary
    except Exception as e:
        logger.error(f"❌ Init Failed: {e}")
        return None

init_gemini()

async def analyze_escalation(guest_name, text_input):
    global model_primary, model_backup
    
    if not model_primary: init_gemini()

    # UPDATED PROMPT: Asks for a specific 'verbal_response'
    prompt = f"""
    You are Grace, a hotel manager.
    Guest: {guest_name}
    Message: "{text_input}"
    
    Output JSON only:
    {{
        "priority": "High/Medium/Low",
        "action_plan": "Internal note for staff (e.g., Send housekeeping)",
        "verbal_response": "Polite reply to speak to the guest (e.g., I have sent housekeeping to your room)."
    }}
    """

    # 1. Try Primary
    try:
        response = await asyncio.to_thread(model_primary.generate_content, prompt)
        return parse_json(response.text)
    except Exception as e:
        logger.warning(f"⚠️ Primary Brain Failed ({e}). Switching to Backup...")

    # 2. Try Backup
    try:
        response = await asyncio.to_thread(model_backup.generate_content, prompt)
        return parse_json(response.text)
    except Exception as e:
        logger.error(f"❌ All Brains Failed: {e}")
        return {
            "priority": "Medium",
            "action_plan": "System Error - Manual check required",
            "verbal_response": "I am having trouble connecting to the system, but I have logged your request."
        }

def parse_json(text):
    try:
        clean = text.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean)
        # Compatibility: Map verbal_response to action_plan if missing, so she speaks something.
        if "verbal_response" in data:
            data["action_plan"] = data["verbal_response"] 
        return data
    except:
        return {
            "priority": "Medium", 
            "action_plan": text, # Fallback: just read the raw text
            "verbal_response": "I have logged your request."
        }
