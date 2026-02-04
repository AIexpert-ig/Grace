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
RETELL_API_KEY = os.getenv("RETELL_API_KEY") 
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or "grace-ai.up.railway.app"
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/telegram-webhook"

# --- LOGGING ---
logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

# --- BRAIN SETUP (GEMINI) ---
# We wrap this to prevent crashes if llm.py is broken
try:
    from .llm import analyze_escalation
except ImportError:
    logger.error("⚠️ Could not import 'analyze_escalation'. Using fallback.")
    async def analyze_escalation(g, i): return {"priority": "Medium", "sentiment": "Neutral", "action_plan": "AI Offline"}

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
    print("🚀 DUBAI-SYNC-V24: VOICE DEBUG MODE ONLINE") 
    logger.info(f"🚀 GRACE AI [V24.0] | Voice: READY")
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
    except Exception as e: logger.warning(f"⚠️ DB Warning: {e}")
    if TELEGRAM_TOKEN:
        async with httpx.AsyncClient() as client:
            await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root(): return FileResponse('app/static/index.html')
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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

# --- UPDATED WEBSOCKET HANDLER ---
@app.websocket("/llm-websocket")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("📞 Call Connected!")
    
    # 1. Send Initial Greeting
    try:
        first_event = {
            "response_type": "response",
            "response_id": "req_init",
            "content": "Hello, this is Grace. How can I help you?",
            "content_complete": True,
            "end_call": False
        }
        await websocket.send_json(first_event)
        logger.info("📤 Sent Greeting")
    except Exception as e:
        logger.error(f"💥 Error sending greeting: {e}")

    try:
        while True:
            # 2. Listen
            data = await websocket.receive_json()
            
            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][0]["content"]
                logger.info(f"🗣️ Guest said: {user_text}")

                # 3. Brain Processing
                try:
                    logger.info("🧠 Asking Gemini...")
                    ai_result = await analyze_escalation("Voice Guest", user_text)
                    
                    # Create verbal reply
                    plan = ai_result.get('action_plan', 'No plan generated.')
                    priority = ai_result.get('priority', 'Medium')
                    
                    verbal_reply = f"I see. I have logged a {priority} priority request for you. {plan}"
                    logger.info(f"🤖 Gemini Replied: {verbal_reply}")

                    # 4. Speak Back
                    response_event = {
                        "response_type": "response",
                        "response_id": data["response_id"],
                        "content": verbal_reply,
                        "content_complete": True,
                        "end_call": False
                    }
                    await websocket.send_json(response_event)
                    logger.info("📤 Sent Audio Response")
                    
                except Exception as ai_error:
                    logger.error(f"💥 AI CRASHED: {ai_error}")
                    # Fallback so call doesn't hang
                    fallback_event = {
                        "response_type": "response",
                        "response_id": data["response_id"],
                        "content": "I am having trouble connecting to the system, but I heard you.",
                        "content_complete": True,
                        "end_call": False
                    }
                    await websocket.send_json(fallback_event)

    except WebSocketDisconnect:
        logger.info("📞 Call ended by user.")
    except Exception as e:
        logger.error(f"💥 Critical Websocket Error: {e}")

