# DUBAI_SYNC_FORCE_02_FEB_1012
# Force Trigger Deployment - Dubai Sync v1.0
import hmac
import hashlib
import time
import logging
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# Setup "Loud" Logging
logger = logging.getLogger("app.main")
security = HTTPBearer()

async def verify_hmac_signature(request: Request):
    # 1. Extract Headers
    x_grace_signature = request.headers.get("x-grace-signature")
    x_grace_timestamp = request.headers.get("x-grace-timestamp")
    
    if not x_grace_signature or not x_grace_timestamp:
        logger.error("HMAC_ERROR: Missing security headers")
        raise HTTPException(status_code=401, detail="Missing security headers")

    # 2. Prevent Replay Attacks (5 minute window)
    try:
        if abs(time.time() - int(x_grace_timestamp)) > 300:
            logger.error(f"HMAC_ERROR: Timestamp expired. Server time: {int(time.time())}, Received: {x_grace_timestamp}")
            raise HTTPException(status_code=401, detail="Timestamp expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp format")

    # 3. Get the raw body
    body_bytes = await request.body()
    body_str = body_bytes.decode()

    # 4. THE DOT PROTOCOL Math
    payload = f"{x_grace_timestamp}.{body_str}"
    
    expected = hmac.new(
        settings.HMAC_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    # 5. FORCED LOGGING - Reveal the truth in Railway logs
    logger.error(f"HMAC_DEBUG: Payload used: '{payload}'")
    logger.error(f"HMAC_DEBUG: Expected Sig: {expected}")
    logger.error(f"HMAC_DEBUG: Received Sig: {x_grace_signature}")

    # 6. Final Validation
    if not hmac.compare_digest(expected, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return True

async def get_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    if auth.credentials != settings.API_KEY:
        logger.error(f"AUTH_ERROR: Invalid Bearer Token. Received: {auth.credentials}")
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return auth.credentials