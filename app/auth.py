import hmac
import hashlib
import time
import os
from fastapi import Request, HTTPException, Header

# Load from Railway environment variable
API_SECRET_KEY = os.getenv("HMAC_SECRET")

async def verify_hmac_signature(
    request: Request,
    x_grace_signature: str = Header(...),
    x_grace_timestamp: str = Header(...)
):
    if not API_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Server security configuration missing")

    # Replay protection: 5-minute window
    if abs(int(time.time()) - int(x_grace_timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Security timestamp expired")

    body = await request.body()
    # Ensure decoding matches the simulation's encoding
    payload = f"{x_grace_timestamp}.{body.decode('utf-8')}".encode('utf-8')
    
    expected = hmac.new(
        API_SECRET_KEY.encode('utf-8'), 
        payload, 
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return True