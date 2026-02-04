import os
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from datetime import datetime

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hotel_ai")

DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")

# Fix Postgres URL for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- GLOBAL DATABASE ENGINE (Fixes connection leak) ---
engine = None
if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
    except Exception as e:
        logger.error(f"❌ Failed to create engine: {e}")

# --- LLM IMPORT ---
try:
    from .llm import analyze_escalation
except ImportError:
    logger.warning("⚠️ Could not import analyze_escalation, using fallback mode.")
    async def analyze_escalation(transcript: str) -> dict:
        return {
            "verbal_response": "I understand. I am looking into that for you now.",
            "action_plan": "Fallback response triggered",
            "escalate": False
        }

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Hotel AI Concierge...")
    
    # Initialize DB Tables
    if engine:
        try:
            with engine.begin() as conn: # 'begin' automatically commits
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS escalations (
                        id SERIAL PRIMARY KEY,
                        call_id VARCHAR(255),
                        guest_request TEXT,
                        ai_analysis TEXT,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
            logger.info("✅ Database connected and tables verified.")
        except Exception as e:
            logger.error(f"❌ Database init failed: {e}")
    else:
        logger.warning("⚠️ No DATABASE_URL found. Running in stateless mode.")
        
    yield
    logger.info("🛑 Shutting down...")

app = FastAPI(lifespan=lifespan)

# --- CORS CONFIGURATION (RESTORED) ---
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

# Mount Static Files (Safe Mode)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    logger.warning("⚠️ 'static' directory missing. Web interface will not load.")

# --- ROUTES ---

@app.get("/")
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"status": "online", "service": "Hotel AI Concierge"}

@app.get("/staff/dashboard-stats")
async def dashboard_stats():
    if not engine: return {"error": "No database"}
    try:
        with engine.connect() as conn:
            # Using text() explicitly for safety
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress
                FROM escalations
            """))
            row = result.fetchone()
            return {
                "total_tickets": row[0] or 0,
                "pending": row[1] or 0,
                "resolved": row[2] or 0,
                "in_progress": row[3] or 0
            }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return {"error": "Database error"}

@app.get("/staff/recent-tickets")
async def recent_tickets():
    if not engine: return []
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, call_id, guest_request, ai_analysis, status, created_at
                FROM escalations ORDER BY created_at DESC LIMIT 50
            """))
            return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error(f"Tickets error: {e}")
        return []

@app.post("/staff/escalate")
async def manual_escalate(request: Request):
    if not engine: raise HTTPException(500, "Database unavailable")
    try:
        data = await request.json()
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO escalations (call_id, guest_request, ai_analysis, status)
                VALUES (:cid, :req, :ai, 'pending')
            """), {
                "cid": data.get("call_id", "manual"),
                "req": data.get("guest_request", ""),
                "ai": "Manual Escalation"
            })
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Escalate error: {e}")
        raise HTTPException(500, str(e))

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    logger.info(f"Telegram: {data}")
    return {"status": "received"}

# --- WEBSOCKET HANDLER ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info(f"📞 Call Connected: {call_id}")
    
    conversation_history = []
    
    try:
        # Send initial greeting
        await websocket.send_json({
            "response_type": "response",
            "response_id": 0,
            "content": "Good evening! Welcome to our hotel. How may I assist you today?",
            "content_complete": True,
            "end_call": False
        })
        
        while True:
            data = await websocket.receive_json()
            
            if data.get("interaction_type") == "response_required":
                transcript = data.get("transcript", [])
                if not transcript or not isinstance(transcript, list):
                    continue

                # Safely get last user message
                last_utterance = transcript[-1]
                user_message = last_utterance.get("content", "")
                if not user_message: continue

                logger.info(f"🗣️ User ({call_id}): {user_message}")
                
                # Build context
                conversation_history.append(f"User: {user_message}")
                full_context = "\n".join(conversation_history[-10:]) # Keep last 10 turns
                
                # Analyze
                ai_result = await analyze_escalation(full_context)
                verbal_response = ai_result.get("verbal_response", "I see. Could you say that again?")
                
                conversation_history.append(f"AI: {verbal_response}")

                # Database logging (Non-blocking ideally, but blocking here for simplicity)
                if ai_result.get("escalate", False) and engine:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("""
                                INSERT INTO escalations (call_id, guest_request, ai_analysis, status)
                                VALUES (:cid, :req, :ai, 'pending')
                            """), {
                                "cid": call_id,
                                "req": user_message,
                                "ai": json.dumps(ai_result)
                            })
                    except Exception as db_e:
                        logger.error(f"DB Logging failed: {db_e}")

                # Send Response
                # Note: Use incoming response_id if available to keep sync
                req_id = data.get("response_id", 0) 
                await websocket.send_json({
                    "response_type": "response",
                    "response_id": req_id,
                    "content": verbal_response,
                    "content_complete": True,
                    "end_call": False
                })

    except WebSocketDisconnect:
        logger.info(f"📞 Call Ended: {call_id}")
    except Exception as e:
        logger.error(f"🔥 WebSocket Crash: {e}")