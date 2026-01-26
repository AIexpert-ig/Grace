import hmac
import hashlib
import time
import os
from fastapi import Request, HTTPException, Header

# Loaded from Railway/Environment Variables
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "default_secret_for_lab")

async def verify_hmac_signature(
    request: Request,
    x_grace_signature: str = Header(...),
    x_grace_timestamp: str = Header(...)
):
    # Replay protection: 5-minute window
    if abs(int(time.time()) - int(x_grace_timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Security timestamp expired")

    body = await request.body()
    payload = f"{x_grace_timestamp}.{body.decode()}".encode()
    
    expected = hmac.new(
        API_SECRET_KEY.encode(), 
        payload, 
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return True