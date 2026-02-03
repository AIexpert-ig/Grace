import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from .auth import verify_hmac_signature

# --- IMPORT THE BRAIN ---
try:
    from .llm import analyze_escalation
except ImportError:
    # Fallback to prevent crash if LLM fails
    async def analyze_escalation(g, i):
        return {"priority": "Medium", "sentiment": "Neutral", "action_plan": "AI Offline"}

logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

# --- DATABASE SETUP ---
DATABASE_URL = os.getenv("DATABASE_URL")

def get_engine():
    if not DATABASE_URL:
        logger.error("❌ DATABASE_URL is missing!")
        raise ValueError("DATABASE_URL is not set")
    return create_engine(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # FORCE SYNC V15.0
    print("🚀 DUBAI-SYNC-V15: SYSTEM STARTING") 
    logger.info("🚀 GRACE AI Infrastructure Online [V15.0-DUBAI-MASTER]")
    
    # Auto-Heal: Ensure DB table exists on startup
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS escalations (
                    id SERIAL PRIMARY KEY,
                    guest_name VARCHAR,
                    room_number VARCHAR,
                    issue TEXT,
                    status VARCHAR DEFAULT 'OPEN',
                    sentiment VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            logger.info("✅ Database Schema Verified")
    except Exception as e:
        logger.warning(f"⚠️ DB Setup Warning: {e}")
    yield

app = FastAPI(lifespan=lifespan)

# --- CORS CONFIGURATION ---
origins = [
    "https://grace-dxb.up.railway.app",  # Production frontend
    "http://localhost:3000",              # Local dev
    "http://127.0.0.1:3000",              # Local dev
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. DASHBOARD STATS ENDPOINT (The Missing Piece) ---
@app.get("/staff/dashboard-stats")
async def get_dashboard_stats():
    """
    Returns real-time stats for the frontend dashboard.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Count total tickets
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            
            # Count open tickets
            pending = conn.execute(text("SELECT COUNT(*) FROM escalations WHERE status = 'OPEN'")).scalar()
            
            # Count negative sentiment (Angry guests)
            critical = conn.execute(text("SELECT COUNT(*) FROM escalations WHERE sentiment = 'NEGATIVE'")).scalar()

            return {
                "total_tickets": total or 0,
                "pending_tickets": pending or 0,
                "resolved_tickets": (total - pending) if total else 0,
                "vip_guests": critical or 0  # Using 'Negative' as proxy for Critical attention needed
            }
    except Exception as e:
        logger.error(f"❌ Dashboard Stats Failed: {e}")
        # Return zeros instead of crashing, so dashboard still loads
        return {
            "total_tickets": 0,
            "pending_tickets": 0,
            "resolved_tickets": 0,
            "vip_guests": 0
        }

# --- 2. ESCALATION ENDPOINT ---
@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    try:
        data = await request.json()
        guest = data.get("guest_name", "Unknown")
        issue = data.get("issue", "No issue provided")

        # 🧠 ASK THE BRAIN
        logger.info(f"🧠 AI Analyzing issue for {guest}...")
        ai_result = await analyze_escalation(guest, issue)
        
        # Log the Intelligence
        logger.info(f"🤖 VERDICT: {ai_result.get('priority')} | PLAN: {ai_result.get('action_plan')}")

        # Save to DB
        engine = get_engine()
        with engine.begin() as conn:
            # Combine issue + plan for visibility
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
            
        return {"status": "dispatched", "ai_analysis": ai_result}

    except Exception as e:
        logger.error(f"❌ Escalation Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"status": "Grace AI Online", "cors_enabled": True}