import hmac
import hashlib
import json
import time
import requests

# CONFIGURATION
SECRET_KEY = "grace_prod_key_99"
URL = "https://grace-ai.up.railway.app/staff/escalate"

# PAYLOAD
payload_data = {
    "guest_name": "Sheikh Ahmed",
    "room_number": "Royal Suite 1",
    "issue": "Security Protocol Verified. VIP escalation engine is now online.",
    "is_vip": True,
    "sentiment": "CRITICAL"
}

def generate_signature(secret, timestamp, data_dict):
    # Canonicalize: No spaces, sorted keys (Matches Server Logic)
    canonical_body = json.dumps(data_dict, separators=(",", ":"), sort_keys=True)
    to_sign = f"{timestamp}.{canonical_body}"
    signature = hmac.new(secret.encode(), to_sign.encode(), hashlib.sha256).hexdigest()
    return signature, canonical_body

def send_escalation():
    timestamp = str(int(time.time()))
    signature, body_str = generate_signature(SECRET_KEY, timestamp, payload_data)
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SECRET_KEY}",
        "x-grace-timestamp": timestamp,
        "x-grace-signature": signature
    }

    print(f"🚀 Sending Request to AI Brain...")
    try:
        response = requests.post(URL, headers=headers, data=body_str)
        print(f"\n📨 STATUS: {response.status_code}")
        print(f"📄 RESPONSE: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_escalation()