import hmac
import hashlib
import time
import logging
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

logger = logging.getLogger("app.main")
security = HTTPBearer()

async def verify_hmac_signature(request: Request):
    x_grace_signature = request.headers.get("x-grace-signature")
    x_grace_timestamp = request.headers.get("x-grace-timestamp")
    
    if not x_grace_signature or not x_grace_timestamp:
        logger.error("HMAC_ERROR: Missing security headers")
        raise HTTPException(status_code=401, detail="Missing security headers")

    body_bytes = await request.body()
    body_str = body_bytes.decode()

    # THE DOT PROTOCOL Math
    payload = f"{x_grace_timestamp}.{body_str}"
    expected = hmac.new(
        settings.HMAC_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    # FORCED LOGGING - Reveal the truth in Railway logs
    logger.error(f"HMAC_DEBUG: Payload used: '{payload}'")
    logger.error(f"HMAC_DEBUG: Expected Sig: {expected}")
    logger.error(f"HMAC_DEBUG: Received Sig: {x_grace_signature}")

    if not hmac.compare_digest(expected, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return True

async def get_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    if auth.credentials != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return auth.credentials# Force Sync: Mon Feb  2 10:46:05 +04 2026
