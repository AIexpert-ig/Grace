import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from .auth import verify_hmac_signature

# --- CONFIG ---
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# Note: Railway automatically provides this URL
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or "grace-ai.up.railway.app"
WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/telegram-webhook"

# --- LOGGING ---
logger = logging.getLogger("app.main")
logging.basicConfig(level=logging.INFO)

# --- BRAIN SETUP ---
try:
    from .llm import analyze_escalation
except ImportError:
    async def analyze_escalation(g, i): return {"priority": "Medium", "sentiment": "Neutral", "action_plan": "AI Offline"}

def get_engine():
    if not DATABASE_URL: raise ValueError("DATABASE_URL is not set")
    return create_engine(DATABASE_URL)

# --- TELEGRAM UTILS ---
async def send_telegram_reply(chat_id, text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 DUBAI-SYNC-V20: GUEST INTERFACE ONLINE") 
    logger.info(f"🚀 GRACE AI [V20.0] | Telegram: {'ENABLED' if TELEGRAM_TOKEN else 'DISABLED'}")
    
    # 1. Database Check
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
            logger.info("✅ DB Verified")
    except Exception as e: logger.warning(f"⚠️ DB Warning: {e}")

    # 2. Set Telegram Webhook (Auto-Connect)
    if TELEGRAM_TOKEN:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}")
            logger.info(f"📡 Telegram Webhook Set: {resp.status_code} | {resp.text}")

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

# --- NEW: TELEGRAM WEBHOOK ---
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        # Extract message
        if "message" not in data: return {"status": "ignored"}
        
        chat_id = data["message"]["chat"]["id"]
        text_content = data["message"].get("text", "")
        guest_name = data["message"]["from"].get("first_name", "Telegram Guest")

        if not text_content: return {"status": "no text"}

        # 1. Ask the Brain
        logger.info(f"📩 Telegram from {guest_name}: {text_content}")
        # Send "Thinking" indicator
        await send_telegram_reply(chat_id, "Grace is thinking...")
        
        ai_result = await analyze_escalation(guest_name, text_content)
        action_plan = ai_result.get("action_plan", "I have logged your request.")

        # 2. Save to DB (So Dashboard sees it)
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
            {"g": f"{guest_name} (Telegram)", "r": "Online", "i": f"{text_content} || [AI: {action_plan}]", "s": "OPEN", "sent": ai_result.get("sentiment")})

        # 3. Reply to Guest
        await send_telegram_reply(chat_id, f"✅ Request Logged.\n\nPlan: {action_plan}")

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Telegram Error: {e}")
        return {"status": "error"}
