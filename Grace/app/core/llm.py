import os
import google.generativeai as genai
import json

# Configure the Brain
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

async def analyze_escalation(guest_name: str, issue_text: str):
    """
    Uses Google Gemini (Free) to analyze the severity of a guest request.
    """
    if not api_key:
        print("⚠️ GEMINI_API_KEY missing. Skipping AI analysis.")
        return {"sentiment": "UNKNOWN", "priority": "MEDIUM", "action_plan": "Manual review required"}

    # Change 'gemini-1.5-flash' to:
    model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    You are the AI Concierge for a 7-star Ultra-Luxury Hotel.
    Analyze this guest issue:
    Guest: {guest_name}
    Issue: "{issue_text}"

    Return JSON ONLY with these fields:
    - sentiment: (POSITIVE, NEUTRAL, NEGATIVE, CRITICAL)
    - priority: (LOW, MEDIUM, HIGH, IMMEDIATE)
    - action_plan: A 1-sentence instruction for staff.
    """

    try:
        response = model.generate_content(prompt)
        # Clean the text to ensure it's valid JSON (remove markdown ticks if present)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ AI Analysis Failed: {e}")
        return {"sentiment": "ERROR", "priority": "HIGH", "action_plan": "AI Offline - Check immediately"}
