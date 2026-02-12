import os
import json
import uuid
import logging
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from app.core.config import settings
from app.core.events import bus, logger
from app.services.telegram_bot import handle_ticket_created
from app.services.make_integration import handle_make_trigger

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

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

if settings.google_api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.google_api_key)
    except Exception as exc:
        logger.debug("Google GenerativeAI import/config failed: %s", exc)

@app.on_event("startup")
async def startup():
    bus.subscribe("ticket.created", handle_ticket_created)
    bus.subscribe("ticket.created", handle_make_trigger)
    logger.info("Grace AI Event Bus Online")

@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")

@app.get("/health")
def health_check():
    return {"status": "healthy", "env": settings.ENV}

@app.get("/staff/recent-tickets")
def get_recent_tickets():
    db = SessionLocal()
    try:
        tickets = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(20).all()
        return [{"id": t.id, "guest_name": t.guest_name, "room_number": t.room_number, "issue": t.issue, "status": t.status, "sentiment": t.sentiment, "created_at": t.created_at.isoformat()} for t in tickets]
    finally:
        db.close()

@app.get("/staff/dashboard-stats")
def get_stats():
    db = SessionLocal()
    try:
        return {
            "total_tickets": db.query(Escalation).count(),
            "open_tickets": db.query(Escalation).filter(Escalation.status == "OPEN").count(),
            "sentiment_score": 98
        }
    finally:
        db.close()

@app.post("/staff/escalate")
async def create_ticket(request: Request):
    data = await request.json()
    cid = str(uuid.uuid4())
    db = SessionLocal()
    try:
        new_ticket = Escalation(
            guest_name=data.get("guest_name", "Test Guest"),
            room_number=data.get("room_number", "101"),
            issue=data.get("issue", "Test Issue"),
            status="OPEN",
            sentiment=data.get("sentiment", "Neutral")
        )
        db.add(new_ticket)
        db.commit()
        
        await bus.publish("ticket.created", {
            "guest_name": new_ticket.guest_name,
            "room_number": new_ticket.room_number,
            "issue": new_ticket.issue
        }, cid)
        
        return {"status": "Ticket Created", "correlation_id": cid}
    finally:
        db.close()

@app.delete("/staff/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(Escalation).filter(Escalation.id == ticket_id).first()
        if not ticket: raise HTTPException(404, "Not found")
        db.delete(ticket)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()

# Test Routes
@app.post("/integrations/test/telegram")
async def test_telegram():
    cid = str(uuid.uuid4())
    await bus.publish("ticket.created", {
        "guest_name": "Test Bot", 
        "room_number": "000", 
        "issue": "Connectivity Test"
    }, cid)
    return {"status": "triggered", "correlation_id": cid}

@app.post("/integrations/test/make")
async def test_make():
    cid = str(uuid.uuid4())
    await handle_make_trigger({"type": "test_ping"}, cid)
    return {"status": "triggered", "correlation_id": cid}

# Voice Hook
@app.post("/webhook")
async def handle_webhook(request: Request):
    return {"received": True}

# Telegram Inbound Webhook
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        # Basic logging for now - in a real app we'd parse commands here
        logger.info(f"Telegram Webhook Received: {json.dumps(data)}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Telegram Webhook Error: {e}")
        return {"ok": False}

# Voice WebSocket
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    cid = call_id
    try:
        await websocket.send_json({"response_type": "response", "response_id": "init", "content": "Good morning, Grace speaking.", "content_complete": True, "end_call": False})
        while True:
            data = await websocket.receive_json()
            if data.get("interaction_type") == "response_required":
                user_text = data["transcript"][-1]["content"]
                
                ai_reply = "I've noted that request."
                try:
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(f"You are a hotel concierge. User: {user_text}. Keep it short.")
                    ai_reply = response.text
                except: pass

                if len(user_text) > 5:
                    db = SessionLocal()
                    try:
                        t = Escalation(guest_name="Voice Guest", room_number="Unknown", issue=user_text, status="OPEN", sentiment="Neutral")
                        db.add(t)
                        db.commit()
                        await bus.publish("ticket.created", {"guest_name": "Voice Guest", "issue": user_text}, cid)
                    finally:
                        db.close()

                await websocket.send_json({"response_type": "response", "response_id": data["response_id"], "content": ai_reply, "content_complete": True, "end_call": False})
    except Exception:
        pass
