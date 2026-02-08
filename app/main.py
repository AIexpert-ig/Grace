import os
import json
from datetime import datetime

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

import google.generativeai as genai  # pylint: disable=import-error

# --- CONFIGURATION ---
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/railway"
)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- DATABASE SETUP ---
Base = declarative_base()


class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, default="Unknown Guest")
    room_number = Column(String, default="Unknown")
    issue = Column(Text)
    status = Column(String, default="OPEN")
    sentiment = Column(String, default="Neutral")
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FASTAPI APP ---
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# --- AI SETUP ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- ROUTES ---


@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Grace Hotel AI"}


# --- DASHBOARD API ENDPOINTS ---


@app.get("/staff/recent-tickets")
def get_recent_tickets():
    db = SessionLocal()
    try:
        tickets = (
            db.query(Escalation)
            .order_by(Escalation.created_at.desc())
            .limit(10)
            .all()
        )
        return [
            {
                "id": t.id,
                "guest_name": t.guest_name,
                "room_number": t.room_number,
                "issue": t.issue,
                "status": t.status,
                "sentiment": t.sentiment,
                "created_at": t.created_at.isoformat(),
            }
            for t in tickets
        ]
    finally:
        db.close()


@app.get("/staff/dashboard-stats")
def get_stats():
    db = SessionLocal()
    try:
        total = db.query(Escalation).count()
        open_tickets = db.query(Escalation).filter(Escalation.status == "OPEN").count()
        return {
            "total_tickets": total,
            "open_tickets": open_tickets,
            "sentiment_score": 98,
        }
    finally:
        db.close()


@app.post("/staff/escalate")
async def create_ticket(request: Request):
    data = await request.json()
    db = SessionLocal()
    try:
        new_ticket = Escalation(
            guest_name=data.get("guest_name", "Test Guest"),
            room_number=data.get("room_number", "101"),
            issue=data.get("issue", "Test Issue"),
            status="OPEN",
            sentiment=data.get("sentiment", "Neutral"),
        )
        db.add(new_ticket)
        db.commit()
        return {"status": "Ticket Created"}
    finally:
        db.close()


# --- WEBHOOK ---
@app.post("/webhook")
async def handle_webhook(request: Request):
    payload = await request.json()
    print(f"📝 WEBHOOK RECEIVED: {json.dumps(payload)}")

    call_summary = payload.get("call_analysis", {}).get(
        "call_summary", "No summary provided."
    )
    sentiment = payload.get("call_analysis", {}).get("user_sentiment", "Neutral")

    db = SessionLocal()
    try:
        ticket = Escalation(
            guest_name="Voice Guest",
            room_number="Unknown",
            issue=call_summary,
            status="OPEN",
            sentiment=sentiment,
        )
        db.add(ticket)
        db.commit()
        print("✅ Ticket Saved to DB")
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        db.close()

    return {"received": True}


# --- VOICE BRAIN (WEBSOCKET) ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    print(f"🧠 AI Connected: {call_id}")

    try:
        welcome_event = {
            "response_type": "response",
            "response_id": "init_welcome",
            "content": "Good morning, this is Grace at the front desk. How may I assist you?",
            "content_complete": True,
            "end_call": False,
        }
        await websocket.send_json(welcome_event)

        while True:
            data = await websocket.receive_json()

            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][-1]["content"]
                print(f"🗣️ User: {user_text}")

                ai_reply = "I have noted that request for you."
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    response = model.generate_content(
                        "You are a hotel concierge named Grace. "
                        f"User says: {user_text}. Keep it short."
                    )
                    ai_reply = response.text
                except Exception:
                    ai_reply = "Certainly, I will take care of that right away."

                response_event = {
                    "response_type": "response",
                    "response_id": data["response_id"],
                    "content": ai_reply,
                    "content_complete": True,
                    "end_call": False,
                }
                await websocket.send_json(response_event)

    except Exception as e:
        print(f"⚠️ Connection Closed: {e}")
