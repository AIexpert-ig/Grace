import hmac
import hashlib
import json
import logging
from fastapi import Request, HTTPException, Header

# DUBAI MASTER AUTH - DIRECT CLOUD INJECT
# Hardcoded key to guarantee match with your script
SECRET_KEY = "grace_prod_key_99"
logger = logging.getLogger("app.auth")

async def verify_hmac_signature(
    request: Request,
    x_grace_signature: str = Header(None),
    x_grace_timestamp: str = Header(None)
):
    if not x_grace_signature or not x_grace_timestamp:
        raise HTTPException(status_code=401, detail="Missing Headers")

    # 1. Read body
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    
    # 2. Reconstruct the exact payload string
    # Try removing whitespace to handle JSON formatting differences
    try:
        json_obj = json.loads(body_str)
        # Compact JSON separators are critical for matching
        clean_body = json.dumps(json_obj, separators=(",", ":"), sort_keys=True)
    except:
        clean_body = body_str

    payload = f"{x_grace_timestamp}.{clean_body}"

    # 3. Calculate Signature
    expected_sig = hmac.new(
        SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    # 4. THE CHEAT CODE - Print everything to logs
    logger.error(f"HMAC_DEBUG: SECRET_KEY used: '{SECRET_KEY}'")
    logger.error(f"HMAC_DEBUG: Payload used: '{payload}'")
    logger.error(f"HMAC_DEBUG: Received Sig: {x_grace_signature}")
    logger.error(f"HMAC_DEBUG: Expected Sig: {expected_sig}")

    if not hmac.compare_digest(expected_sig, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    
    return True
