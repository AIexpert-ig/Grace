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
        return {"priority": "Medium", "verbal_response": "I have logged your request.", "action_plan": "Manual Check", "sentiment": "Neutral"}

def get_engine():
    if not DATABASE_URL: return None
    return create_engine(DATABASE_URL)

async def send_telegram_reply(chat_id, text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text})

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 DUBAI-SYNC-V36: WEBHOOK HANDLER ACTIVE") 
    logger.info(f"🚀 GRACE AI [V36.0] | Ready to Capture Tickets")
    
    try:
        engine = get_engine()
        if engine:
            with engine.begin() as conn:
                conn.execute(text("""CREATE TABLE IF NOT EXISTS escalations (id SERIAL PRIMARY KEY, guest_name VARCHAR, room_number VARCHAR, issue TEXT, status VARCHAR DEFAULT 'OPEN', sentiment VARCHAR, created_at TIMESTAMP DEFAULT NOW());"""))
    except Exception as e: 
        logger.warning(f"⚠️ DB Init Warning: {e}")

    if TELEGRAM_TOKEN:
        async with httpx.AsyncClient() as client:
            await client.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

if os.path.exists("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- ENDPOINTS ---

@app.get("/")
async def read_root(): 
    if os.path.exists("app/static/index.html"):
        return FileResponse('app/static/index.html')
    return {"status": "Grace AI Online"}

# --- THE NEW WEBHOOK HANDLER (Captures the Summary) ---
@app.post("/webhook") 
async def retell_webhook(request: Request):
    try:
        payload = await request.json()
        event = payload.get("event")
        
        # Only act when the analysis is ready
        if event == "call_analyzed":
            call_data = payload.get("call", {})
            analysis = call_data.get("call_analysis", {})
            
            # Extract Details from Retell Summary
            summary = analysis.get("call_summary", "No summary provided.")
            sentiment = analysis.get("user_sentiment", "Neutral")
            
            # Try to parse Name/Room from the summary if possible, otherwise generic
            guest_name = "Voice Guest"
            room_num = "Phone"
            
            # Save to Dashboard
            engine = get_engine()
            if engine:
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO escalations (guest_name, room_number, issue, status, sentiment) VALUES (:g, :r, :i, :s, :sent)"), 
                    {"g": guest_name, "r": room_num, "i": f"{summary}", "s": "OPEN", "sent": sentiment})
            
            logger.info(f"✅ Ticket Created from Voice Call: {summary}")

        return JSONResponse(content={"received": True})
    except Exception as e:
        logger.error(f"Webhook Error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

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

# --- VOICE HANDLER ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    
    try:
        await websocket.send_json({
            "response_type": "response",
            "response_id": "req_init",
            "content": "Hello, this is Grace, the hotel manager. How can I help you?",
            "content_complete": True,
            "end_call": False
        })

        while True:
            data = await websocket.receive_json()
            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][0]["content"]
                
                # We do NOT save to DB here anymore (too noisy).
                # We wait for the Webhook to save the full summary.

                ai_result = await analyze_escalation("Voice Guest", user_text)
                verbal_reply = ai_result.get('verbal_response', ai_result.get('action_plan', 'I have logged your request.'))
                
                await websocket.send_json({
                    "response_type": "response",
                    "response_id": data["response_id"],
                    "content": verbal_reply,
                    "content_complete": True,
                    "end_call": False
                })

    except WebSocketDisconnect:
        pass
