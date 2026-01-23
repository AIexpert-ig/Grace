"""HMAC signature validation with request body reading."""
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Request, HTTPException, status

from .config import settings


async def verify_hmac_signature(request: Request) -> dict[str, Any]:
    """Verify HMAC signature and return parsed body.
    
    This dependency reads the request body, verifies the HMAC signature,
    and returns the parsed JSON body. This prevents the endpoint from
    needing to read the body again.
    
    Args:
        request: FastAPI request object
        
    Returns:
        dict: Parsed JSON body from the request
        
    Raises:
        HTTPException: If signature is invalid or timestamp is invalid
    """
    # Get signature and timestamp from headers
    signature = request.headers.get("X-Signature")
    timestamp_str = request.headers.get("X-Timestamp")
    
    if not signature or not timestamp_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Signature or X-Timestamp header"
        )
    
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timestamp format"
        )
    
    # Prevent replay attacks: reject requests older than 5 minutes
    current_time = int(time.time())
    if abs(current_time - timestamp) > 300:  # 5 minutes
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Request timestamp is too old or too far in the future"
        )
    
    # Read request body
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # Compute expected signature: HMAC-SHA256(secret, timestamp + body)
    message = f"{timestamp}{body_str}"
    expected_signature = hmac.new(
        settings.HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature"
        )
    
    # Parse and return the body
    try:
        return json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body"
        )
