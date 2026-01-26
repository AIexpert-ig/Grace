import requests
import hmac
import hashlib
import time
import json

# LOCAL TESTING CONFIGURATION
BASE_URL = "http://localhost:8000" 
SECRET_KEY = "grace_hmac_secret_99"
ENDPOINT = "/staff/escalate"

def trigger_lab_escalation():
    timestamp = str(int(time.time()))
    payload = {
        "guest_name": "Alexander Knight",
        "room_number": "1104",
        "issue": "Immediate medical assistance required - non-emergency triage"
    }
    
    # Use separators to remove spaces: {"key":"value"} instead of {"key": "value"}
    body_json = json.dumps(payload, separators=(',', ':'))
    message = f"{timestamp}.{body_json}".encode('utf-8')
    
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "x-grace-signature": signature,
        "x-grace-timestamp": timestamp,
        "Content-Type": "application/json"
    }
    
    print(f"--- LOCAL TEST: AUTHENTICATED HANDSHAKE ---")
    print(f"Endpoint: {BASE_URL}{ENDPOINT}")
    response = requests.post(f"{BASE_URL}{ENDPOINT}", headers=headers, data=body_json)
    
    if response.status_code == 200:
        print(f"✅ SUCCESS: 200 OK")
        print(f"GRACE RESPONSE: {response.json()}")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(f"REASON: {response.text}")

if __name__ == "__main__":
    trigger_lab_escalation()
