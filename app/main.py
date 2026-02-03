import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from .auth import verify_hmac_signature

# --- BRAIN SETUP ---
try:
    from .llm import analyze_escalation
except ImportError:
    async def analyze_escalation(g, i): return {"priority": "Medium", "sentiment": "Neutral", "action_plan": "AI Offline"}

logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv("DATABASE_URL")
def get_engine():
    if not DATABASE_URL: raise ValueError("DATABASE_URL is not set")
    return create_engine(DATABASE_URL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 DUBAI-SYNC-V19: UI LAUNCH") 
    logger.info("🚀 GRACE AI UI Online [V19.0]")
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
            logger.info("✅ DB Verified")
    except Exception as e: logger.warning(f"⚠️ DB Warning: {e}")
    yield

app = FastAPI(lifespan=lifespan)

# --- SERVE UI ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse('app/static/index.html')

# --- API ENDPOINTS ---
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/staff/dashboard-stats")
async def get_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            return {"total_tickets": total or 0}
    except Exception: return {"total_tickets": 0}

@app.post("/staff/escalate")
async def escalate(request: Request):
    # Note: Auth temporarily bypassed for the UI demo.
    # To re-enable, add: authenticated: bool = Depends(verify_hmac_signature)
    try:
        data = await request.json()
        guest, issue = data.get("guest_name"), data.get("issue")
        ai_result = await analyze_escalation(guest, issue)
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
            {"g": guest, "r": data.get("room_number"), "i": f"{issue} || [AI: {ai_result.get('action_plan')}]", "s": "OPEN", "sent": ai_result.get('sentiment')})
        return {"status": "dispatched", "ai_analysis": ai_result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
