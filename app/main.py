import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

# --- AUTH BYPASS FOR TESTING ---
# We define a dummy verifier that always says "YES"
async def verify_hmac_signature(request: Request):
    return True

# --- IMPORT THE BRAIN ---
try:
    from .llm import analyze_escalation
except ImportError:
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
    # FORCE SYNC V17.0 (AUTH BYPASS)
    print("🚀 DUBAI-SYNC-V17: SYSTEM STARTING - TEST MODE") 
    logger.info("🚀 GRACE AI Infrastructure Online [V17.0-TEST-MODE]")
    
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
    "https://grace-dxb.up.railway.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DASHBOARD ENDPOINT ---
@app.get("/staff/dashboard-stats")
async def get_dashboard_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            pending = conn.execute(text("SELECT COUNT(*) FROM escalations WHERE status = 'OPEN'")).scalar()
            critical = conn.execute(text("SELECT COUNT(*) FROM escalations WHERE sentiment = 'NEGATIVE'")).scalar()

            return {
                "total_tickets": total or 0,
                "pending_tickets": pending or 0,
                "resolved_tickets": (total - pending) if total else 0,
                "vip_guests": critical or 0
            }
    except Exception as e:
        logger.error(f"❌ Dashboard Stats Failed: {e}")
        return {"total_tickets": 0, "pending_tickets": 0, "resolved_tickets": 0, "vip_guests": 0}

# --- ESCALATION ENDPOINT (AUTH DISABLED) ---
@app.post("/staff/escalate")
async def escalate(request: Request, authenticated: bool = Depends(verify_hmac_signature)):
    try:
        data = await request.json()
        guest = data.get("guest_name", "Unknown")
        issue = data.get("issue", "No issue provided")

        logger.info(f"🧠 AI Analyzing issue for {guest}...")
        ai_result = await analyze_escalation(guest, issue)
        
        logger.info(f"🤖 VERDICT: {ai_result.get('priority')} | PLAN: {ai_result.get('action_plan')}")

        engine = get_engine()
        with engine.begin() as conn:
            enhanced_issue = f"{issue} || [AI PLAN: {ai_result.get('action_plan')}]"
            conn.execute(text(
                "INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"
            ), {
                "g": guest, "r": data.get("room_number"), "i": enhanced_issue, "s": "OPEN", "sent": ai_result.get('sentiment', 'NEUTRAL')
            })
            
        return {"status": "dispatched", "ai_analysis": ai_result}

    except Exception as e:
        logger.error(f"❌ Escalation Error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"status": "Grace AI Online", "cors_enabled": True}
