import os
import logging
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy import create_engine, text
import json
import time
import hmac
import hashlib

# --- 1. SETUP LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")

# --- 2. IMPORT THE BRAIN (LLM) ---
try:
    from app.core.llm import analyze_escalation
except ImportError:
    from .llm import analyze_escalation

app = FastAPI()

# --- 3. DATABASE SETUP & MIGRATION ---
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "grace_prod_key_99")

def get_engine():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL is not set")
    return create_engine(DATABASE_URL)

@app.on_event("startup")
def startup_db_check():
    """
    The 'Doctor' function: Checks DB health and adds missing columns automatically.
    """
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # 1. Create table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id SERIAL PRIMARY KEY,
                    guest_name VARCHAR NOT NULL,
                    room_number VARCHAR,
                    issue TEXT,
                    status VARCHAR DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            
            # 2. Add 'sentiment' column if missing (The Fix)
            conn.execute(text("ALTER TABLE escalations ADD COLUMN IF NOT EXISTS sentiment VARCHAR;"))
            
            logger.info("✅ Database Schema Verified (Sentiment Column Added)")
    except Exception as e:
        logger.error(f"⚠️ DB Migration Warning: {e}")

# --- 4. SECURITY (HMAC) ---
async def verify_hmac_signature(request: Request):
    signature = request.headers.get("x-grace-signature")
    timestamp = request.headers.get("x-grace-timestamp")
    
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing security headers")
    
    body = await request.body()
    try:
        data = json.loads(body)
        canonical_body = json.dumps(data, separators=(",", ":"), sort_keys=True)
    except:
        canonical_body = body.decode()

    payload = f"{timestamp}.{canonical_body}"
    expected_signature = hmac.new(
        SECRET_KEY.encode(), 
        payload.encode(), 
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")
    return True

# --- 5. THE AI ENDPOINT ---
@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    data = await request.json()
    guest = data.get("guest_name", "Unknown")
    issue = data.get("issue", "No issue provided")

    # 🧠 ACTIVATE THE BRAIN
    logger.info(f"🧠 AI Analyzing issue for {guest}...")
    ai_result = await analyze_escalation(guest, issue)

    # Log the Verdict
    logger.info(f"🤖 AI VERDICT: {ai_result.get('priority', 'UNKNOWN')}")
    logger.info(f"📝 ACTION PLAN: {ai_result.get('action_plan', 'None')}")

    # Save to Database
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Combine issue + plan for storage
            enhanced_issue = f"{issue} || [AI PLAN: {ai_result.get('action_plan')}]"
            
            conn.execute(text(
                "INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"
            ), {
                "g": guest,
                "r": data.get("room_number"),
                "i": enhanced_issue,
                "s": "OPEN",
                "sent": ai_result.get('sentiment', 'NEUTRAL')
            })
    except Exception as e:
        logger.error(f"DB Error: {e}")
        # Return success to client even if DB fails, but warn them
        return {"status": "partial_success", "message": "AI worked, but DB failed", "error": str(e), "ai_analysis": ai_result}

    return {
        "status": "dispatched", 
        "ai_analysis": ai_result
    }
