import os
import json
import logging
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, text

# --- CONFIG ---
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or "grace-ai.up.railway.app"
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/telegram-webhook"

# --- LOGGING ---
logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

# --- BRAIN SETUP ---
try:
    from .llm import analyze_escalation
except ImportError:
    logger.warning("⚠️ Brain module missing. Using dummy mode.")
    async def analyze_escalation(g, i): 
        return {
            "priority": "Medium", 
            "verbal_response": "I have logged your request.",
            "action_plan": "Manual Check",
            "sentiment": "Neutral"
        }

def get_engine():
    if not DATABASE_URL: return None
    return create_engine(DATABASE_URL)

async def send_telegram_reply(chat_id, text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

# --- LIFESPAN (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 DUBAI-SYNC-V35: FULL SYSTEM ONLINE") 
    logger.info(f"🚀 GRACE AI [V35.0] | Brain: ACTIVE | API: ACTIVE")
    
    # Init Database Table
    try:
        engine = get_engine()
        if engine:
            with engine.begin() as conn:
                conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
    except Exception as e: 
        logger.warning(f"⚠️ DB Init Warning: {e}")

    # Init Telegram Webhook
    if TELEGRAM_TOKEN:
        async with httpx.AsyncClient() as client:
            await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    yield

# --- APP INSTANCE (Must be global) ---
app = FastAPI(lifespan=lifespan)

# --- MIDDLEWARE & STATIC ---
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- ENDPOINTS ---

@app.get("/")
async def read_root(): 
    if os.path.exists("app/static/index.html"):
        return FileResponse('app/static/index.html')
    return {"status": "Grace AI Online", "dashboard": "Missing HTML"}

# Fix Retell 410 Errors
@app.post("/webhook") 
async def generic_webhook(request: Request):
    return JSONResponse(content={"received": True})

# --- STAFF DASHBOARD API (Restored!) ---
@app.get("/staff/dashboard-stats")
async def get_stats():
    try:
        engine = get_engine()
        if not engine: return {"total_tickets": 0}
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            return {"total_tickets": total or 0}
    except Exception: return {"total_tickets": 0}

@app.get("/staff/recent-tickets")
async def get_recent_tickets():
    try:
        engine = get_engine()
        if not engine: return []
        with engine.connect() as conn:
            result = conn.execute(text("SELECT guest_name, room_number, issue, status, sentiment, created_at FROM escalations ORDER BY id DESC LIMIT 10"))
            return [dict(row._mapping) for row in result]
    except Exception: return []

@app.post("/staff/escalate")
async def escalate(request: Request):
    try:
        data = await request.json()
        guest, issue = data.get("guest_name"), data.get("issue")
        ai_result = await analyze_escalation(guest, issue)
        engine = get_engine()
        if engine:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                {"g": guest, "r": data.get("room_number"), "i": f"{issue} || [AI: {ai_result.get('action_plan')}]", "s": "OPEN", "sent": ai_result.get('sentiment')})
        return {"status": "dispatched", "ai_analysis": ai_result}
    except Exception: return {"status": "error"}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        if "message" in data and "text" in data["message"]:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"]["text"]
            guest = data["message"]["from"].get("first_name", "Guest")
            await send_telegram_reply(chat_id, "Thinking...")
            ai_result = await analyze_escalation(guest, text)
            
            plan = ai_result.get("action_plan", "Logged.")
            engine = get_engine()
            if engine:
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                    {"g": f"{guest} (Telegram)", "r": "Online", "i": f"{text} || [AI: {plan}]", "s": "OPEN", "sent": ai_result.get("sentiment")})
            await send_telegram_reply(chat_id, f"✅ Plan: {plan}")
        return {"status": "ok"}
    except Exception: return {"status": "error"}

# --- VOICE HANDLER (The Brain) ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info(f"📞 Call Connected: {call_id}")
    
    try:
        # V35 Greeting
        await websocket.send_json({
            "response_type": "response",
            "response_id": "req_init",
            "content": "Hello, this is Grace, the hotel manager. How can I help you?",
            "content_complete": True,
            "end_call": False
        })

        while True:
            data = await websocket.receive_json()
            
            # Respond only when Retell asks
            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][0]["content"]
                logger.info(f"🗣️ Guest: {user_text}")

                ai_result = await analyze_escalation("Voice Guest", user_text)
                verbal_reply = ai_result.get('verbal_response', ai_result.get('action_plan', 'I have logged your request.'))
                
                await websocket.send_json({
                    "response_type": "response",
                    "response_id": data["response_id"],
                    "content": verbal_reply,
                    "content_complete": True,
                    "end_call": False
                })
                logger.info(f"🤖 Grace: {verbal_reply}")

                # Save to DB
                try:
                    engine = get_engine()
                    if engine:
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                            {"g": "Voice Caller", "r": "Phone", "i": f"{user_text}", "s": "OPEN", "sent": "Voice"})
                except Exception as e:
                    logger.error(f"DB Error: {e}")

    except WebSocketDisconnect:
        logger.info("📞 Call Ended")
