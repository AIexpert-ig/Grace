"""HMAC signature validation for webhook authentication."""
import hashlib
import hmac
import time
from typing import Optional

from fastapi import Header, HTTPException, status

from .config import settings


def verify_hmac_signature(
    x_signature: str = Header(..., alias="X-Signature", description="HMAC signature"),
    x_timestamp: str = Header(..., alias="X-Timestamp", description="Request timestamp"),
    body: bytes = b""
) -> bool:
    """Verify HMAC signature for webhook requests.
    
    Implements HMAC-SHA256 signature validation with timestamp verification
    to prevent replay attacks. The signature is computed as:
    HMAC-SHA256(secret, timestamp + body)
    
    Args:
        x_signature: The HMAC signature from the X-Signature header
        x_timestamp: The timestamp from the X-Timestamp header
        body: The raw request body bytes
        
    Returns:
        bool: True if signature is valid
        
    Raises:
        HTTPException: If signature is invalid or timestamp is too old
    """
    try:
        timestamp = int(x_timestamp)
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
    
    # Compute expected signature: HMAC-SHA256(secret, timestamp + body)
    message = f"{timestamp}{body.decode('utf-8')}"
    expected_signature = hmac.new(
        settings.HMAC_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, x_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature"
        )
    
    return True


async def verify_hmac_dependency(
    x_signature: str = Header(..., alias="X-Signature"),
    x_timestamp: str = Header(..., alias="X-Timestamp")
) -> bool:
    """FastAPI dependency for HMAC signature verification.
    
    Note: This is a simplified version. For full body verification,
    you'll need to read the request body separately or use a custom dependency.
    """
    # For now, verify timestamp is present and valid format
    try:
        timestamp = int(x_timestamp)
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Request timestamp is too old or too far in the future"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timestamp format"
        )
    
    return True
