import os
import google.generativeai as genai
import json

# Initialize the Brain
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

async def analyze_escalation(guest_name: str, issue_text: str):
    """
    Analyzing guest request using Gemini 1.5 Flash (Free Tier).
    """
    if not api_key:
        # Fallback if key is missing
        return {"priority": "MEDIUM", "action_plan": "Manual Review (Key Missing)"}

    # The Prompt
    prompt = f"""
    You are the AI Manager of a luxury hotel.
    Guest: {guest_name}
    Issue: "{issue_text}"

    Analyze and return JSON ONLY:
    {{
        "priority": "LOW" | "MEDIUM" | "HIGH" | "IMMEDIATE",
        "action_plan": "Specific 1-sentence instruction for staff",
        "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE"
    }}
    """

    try:
        # Find this:
model = genai.GenerativeModel('gemini-1.5-flash')

# Replace with this:
model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        # Clean markdown if Gemini adds it
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"❌ Brain Freeze: {e}")
        return {"priority": "HIGH", "action_plan": "Error in AI Analysis", "sentiment": "NEGATIVE"}
