import os
import json
import logging
import httpx
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text

# --- CONFIG ---
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
RETELL_API_KEY = os.getenv("RETELL_API_KEY") # We will add this next
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or "grace-ai.up.railway.app"
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/telegram-webhook"

# --- LOGGING ---
logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

# --- BRAIN SETUP (GEMINI) ---
try:
    from .llm import analyze_escalation, ask_gemini_stream
except ImportError:
    # Fallback if llm.py is missing streaming
    async def analyze_escalation(g, i): return {"priority": "Medium", "sentiment": "Neutral", "action_plan": "AI Offline"}
    async def ask_gemini_stream(text): yield "I am currently offline. Please try again later."

def get_engine():
    if not DATABASE_URL: raise ValueError("DATABASE_URL is not set")
    return create_engine(DATABASE_URL)

async def send_telegram_reply(chat_id, text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 DUBAI-SYNC-V23: VOICE INTERFACE ONLINE") 
    logger.info(f"🚀 GRACE AI [V23.0] | Voice: READY")
    
    # Init DB
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
    except Exception as e: logger.warning(f"⚠️ DB Warning: {e}")

    # Init Telegram
    if TELEGRAM_TOKEN:
        async with httpx.AsyncClient() as client:
            await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}")

    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root(): return FileResponse('app/static/index.html')

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- EXISTING ENDPOINTS ---
@app.get("/staff/dashboard-stats")
async def get_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            return {"total_tickets": total or 0}
    except Exception: return {"total_tickets": 0}

@app.get("/staff/recent-tickets")
async def get_recent_tickets():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT guest_name, room_number, issue, status, sentiment, created_at FROM escalations ORDER BY id DESC LIMIT 5"))
            return [dict(row._mapping) for row in result]
    except Exception: return []

@app.post("/staff/escalate")
async def escalate(request: Request):
    try:
        data = await request.json()
        guest, issue = data.get("guest_name"), data.get("issue")
        ai_result = await analyze_escalation(guest, issue)
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
            {"g": guest, "r": data.get("room_number"), "i": f"{issue} || [AI: {ai_result.get('action_plan')}]", "s": "OPEN", "sent": ai_result.get('sentiment')})
        return {"status": "dispatched", "ai_analysis": ai_result}
    except Exception: return {"status": "error"}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    # (Same Telegram logic as before - abbreviated for space)
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
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                {"g": f"{guest} (Telegram)", "r": "Online", "i": f"{text} || [AI: {plan}]", "s": "OPEN", "sent": ai_result.get("sentiment")})
            await send_telegram_reply(chat_id, f"✅ Plan: {plan}")
        return {"status": "ok"}
    except Exception: return {"status": "error"}

# --- NEW: VOICE WEBSOCKET ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info(f"📞 Call started: {call_id}")
    
    # 1. Send Initial Greeting
    first_event = {
        "response_type": "response",
        "response_id": "req_001",
        "content": "Hello, this is Grace, the hotel manager. How can I help you today?",
        "content_complete": True,
        "end_call": False
    }
    await websocket.send_json(first_event)

    try:
        while True:
            # 2. Listen for Guest Audio (Text Transcript)
            data = await websocket.receive_json()
            
            # Retell sends "interaction_response" when user finishes speaking
            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][0]["content"]
                logger.info(f"🗣️ Guest said: {user_text}")

                # 3. Ask Gemini for response
                ai_response_text = ""
                
                # (Simple blocking call for MVP - Streaming is better for speed later)
                # We reuse the logic but ask for a conversational reply
                ai_result = await analyze_escalation("Voice Guest", user_text)
                # We construct a polite verbal reply based on the action plan
                verbal_reply = f"I understand. I have logged a {ai_result.get('priority')} priority ticket. {ai_result.get('action_plan')}"
                
                # 4. Speak back to Guest
                response_event = {
                    "response_type": "response",
                    "response_id": data["response_id"],
                    "content": verbal_reply,
                    "content_complete": True,
                    "end_call": False
                }
                await websocket.send_json(response_event)
                
                # 5. Log to Dashboard
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                    {"g": "Voice Caller", "r": "Phone", "i": f"{user_text} || [AI: {ai_result.get('action_plan')}]", "s": "OPEN", "sent": ai_result.get("sentiment")})

    except WebSocketDisconnect:
        logger.info(f"📞 Call ended: {call_id}")
