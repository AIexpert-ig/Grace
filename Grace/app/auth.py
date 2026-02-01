async def verify_hmac_signature(
    request: Request,
    x_grace_signature: str = Header(...),
    x_grace_timestamp: str = Header(...)
):
    # USE HMAC_SECRET to match your Railway Variable
    secret = settings.HMAC_SECRET 
    
    if not secret:
        print("CRITICAL: HMAC_SECRET is missing from settings!")
        raise HTTPException(status_code=500, detail="Server security configuration missing")

    # Replay protection: 5-minute window
    if abs(int(time.time()) - int(x_grace_timestamp)) > 300:
        raise HTTPException(status_code=401, detail="Security timestamp expired")

    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    # THE DOT FIX: We add the dot here to match your specific logic
    payload = f"{x_grace_timestamp}.{body_str}"
    
    expected = hmac.new(
        secret.encode('utf-8'), 
        payload.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()

    # THE TRUTH LOGS: These will show up in Railway
    print(f"DEBUG: Signing payload: '{payload}'")
    print(f"DEBUG: Received: {x_grace_signature}")
    print(f"DEBUG: Expected: {expected}")

    if not hmac.compare_digest(expected, x_grace_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return True