import os
import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, text
from .auth import verify_hmac_signature

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
    print("🚀 DUBAI-SYNC-V22: TICKET FEED ONLINE") 
    logger.info(f"🚀 GRACE AI [V22.0] | Telegram: {'ENABLED' if TELEGRAM_TOKEN else 'DISABLED'}")
    
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

# --- ENDPOINTS ---
@app.get("/staff/dashboard-stats")
async def get_stats():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
            return {"total_tickets": total or 0}
    except Exception: return {"total_tickets": 0}

# [NEW] Endpoint to get the actual list of tickets
@app.get("/staff/recent-tickets")
async def get_recent_tickets():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Fetch last 5 tickets, newest first
            result = conn.execute(text("SELECT guest_name, room_number, issue, status, sentiment, created_at FROM escalations ORDER BY id DESC LIMIT 5"))
            return [dict(row._mapping) for row in result]
    except Exception as e:
        logger.error(f"Feed Error: {e}")
        return []

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
    except Exception as e: return {"status": "error", "message": str(e)}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        if "message" not in data: return {"status": "ignored"}
        
        chat_id = data["message"]["chat"]["id"]
        text_content = data["message"].get("text", "")
        guest_name = data["message"]["from"].get("first_name", "Telegram Guest")

        if not text_content: return {"status": "no text"}

        # 1. Reply "Thinking"
        await send_telegram_reply(chat_id, "Grace is thinking...")
        
        # 2. Analyze
        ai_result = await analyze_escalation(guest_name, text_content)
        action_plan = ai_result.get("action_plan", "I have logged your request.")

        # 3. Save to DB
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
            {"g": f"{guest_name} (Telegram)", "r": "Online", "i": f"{text_content} || [AI: {action_plan}]", "s": "OPEN", "sent": ai_result.get("sentiment")})

        # 4. Final Reply
        await send_telegram_reply(chat_id, f"✅ Request Logged.\n\nPlan: {action_plan}")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error"}
