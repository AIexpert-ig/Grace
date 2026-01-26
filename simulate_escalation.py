import requests
import hmac
import hashlib
import time
import json

# CONFIGURATION: Ensure these match your live environment
BASE_URL = "https://your-railway-app-name.railway.app"  # Your Railway URL
SECRET_KEY = "your_enterprise_secret_key_here"        # Match your .env
ENDPOINT = "/staff/escalate"

def trigger_lab_escalation():
    timestamp = str(int(time.time()))
    payload = {
        "guest_name": "Alexander Knight",
        "room_number": "1104",
        "issue": "Immediate medical assistance required - non-emergency triage"
    }
    
    # 1. Prepare the signature body
    body_json = json.dumps(payload)
    message = f"{timestamp}.{body_json}".encode()
    
    # 2. Generate the HMAC-SHA256 signature
    signature = hmac.new(
        SECRET_KEY.encode(),
        message,
        hashlib.sha256
    ).hexdigest()
    
    # 3. Execute the authenticated request
    headers = {
        "x-grace-signature": signature,
        "x-grace-timestamp": timestamp,
        "Content-Type": "application/json"
    }
    
    print(f"--- LAUNCHING LABORATORY TEST ---")
    response = requests.post(f"{BASE_URL}{ENDPOINT}", headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"SUCCESS: Escalation received and dispatched.")
        print(f"SYSTEM PREVIEW: \n{response.json().get('message_preview')}")
    else:
        print(f"FAILED: Status {response.status_code}")
        print(f"DETAIL: {response.text}")

if __name__ == "__main__":
    trigger_lab_escalation()