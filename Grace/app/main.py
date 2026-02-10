import os
import hashlib
import json
import time
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import google.generativeai as genai  # pylint: disable=import-error

from app.core.config import settings
from app.core.events import EventEnvelope, bus, logger
from app.core.security import (
    SignatureExpiredError,
    SignatureInvalidError,
    SignatureMissingError,
    verify_hmac_signature,
    verify_retell_signature,
)
from app.services import telegram_bot
from app.services.make_integration import handle_make_trigger, send_make_webhook

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


database_url = settings.database_url_raw
engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FASTAPI APP ---
app = FastAPI()

BUILD_SHA = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GITHUB_SHA") or "unknown"
BUILD_MARK = "grace-build-2026-02-09"

@app.get("/__build")
def __build():
    return {"sha": BUILD_SHA, "mark": BUILD_MARK}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

api_key = getattr(settings, "GOOGLE_API_KEY", None) or getattr(settings, "google_api_key", None)
if api_key:
    genai.configure(api_key=api_key)

@app.on_event("startup")
async def startup() -> None:
    if settings.ENABLE_TELEGRAM:
        bus.subscribe("ticket.created", telegram_bot.handle_ticket_created)
    if settings.ENABLE_MAKE_WEBHOOKS:
        bus.subscribe("ticket.created", handle_make_trigger)
    logger.info("System Online: Event Bus Active", extra={"correlation_id": "startup"})


def _error_response(status_code: int, error: str, correlation_id: str | None = None) -> JSONResponse:
    payload = {"error": error}
    if correlation_id:
        payload["correlation_id"] = correlation_id
    return JSONResponse(status_code=status_code, content=payload)


def _parse_envelope(data: dict) -> EventEnvelope | None:
    try:
        return EventEnvelope(**data)
    except Exception:
        return None


def _derive_retell_type(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("event", "type", "event_type"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "retell.webhook"


# --- ROUTES ---


@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html", media_type="text/html")


@app.get("/health")
def health_check():
    return {"status": "healthy", "env": getattr(settings, "ENV", "dev")}


@app.get("/events/deadletter")
def get_deadletters(request: Request):
    if not settings.ADMIN_TOKEN:
        return _error_response(503, "admin_token_missing")
    if request.headers.get("X-Admin-Token") != settings.ADMIN_TOKEN:
        return _error_response(401, "unauthorized")
    return JSONResponse(status_code=200, content={"deadletters": bus.get_deadletters()})


@app.post("/webhooks/make/in")
async def make_ingress(request: Request):
    if not settings.ENABLE_MAKE_WEBHOOKS:
        raise HTTPException(status_code=404, detail="Not Found")

    if not settings.MAKE_SIGNING_SECRET:
        return _error_response(503, "make_signing_secret_missing")

    raw_body = await request.body()
    timestamp = request.headers.get("X-Signature-Timestamp")
    signature = request.headers.get("X-Signature")

    try:
        verify_hmac_signature(
            raw_body=raw_body,
            timestamp=timestamp,
            signature=signature,
            secret=settings.MAKE_SIGNING_SECRET,
            tolerance_seconds=settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS,
        )
    except SignatureMissingError:
        return _error_response(401, "missing_signature")
    except SignatureExpiredError:
        return _error_response(401, "expired_signature")
    except SignatureInvalidError:
        return _error_response(401, "invalid_signature")

    try:
        data = await request.json()
    except Exception:
        return _error_response(400, "invalid_envelope")

    envelope = _parse_envelope(data)
    if not envelope:
        return _error_response(400, "invalid_envelope")

    result = await bus.publish(envelope)
    if result.status == "duplicate":
        return JSONResponse(
            status_code=200,
            content={"status": "duplicate", "correlation_id": result.correlation_id},
        )

    if settings.ENABLE_TELEGRAM:
        telegram_bot.record_event(envelope)

    return JSONResponse(
        status_code=200,
        content={"status": "accepted", "correlation_id": result.correlation_id},
    )


@app.post("/integrations/make/trigger")
async def make_trigger(request: Request):
    if not settings.ENABLE_MAKE_WEBHOOKS:
        raise HTTPException(status_code=404, detail="Not Found")

    if not settings.ADMIN_TOKEN:
        return _error_response(503, "admin_token_missing")
    if request.headers.get("X-Admin-Token") != settings.ADMIN_TOKEN:
        return _error_response(401, "unauthorized")

    if not settings.MAKE_WEBHOOK_URL:
        return _error_response(503, "make_webhook_url_missing")

    try:
        payload = await request.json()
    except Exception:
        return _error_response(400, "invalid_envelope")

    envelope = _parse_envelope(payload)
    if not envelope:
        return _error_response(400, "invalid_envelope")

    try:
        await send_make_webhook(settings.MAKE_WEBHOOK_URL, envelope)
    except Exception:
        return _error_response(
            502, "make_webhook_failed", correlation_id=envelope.correlation_id
        )

    if settings.ENABLE_TELEGRAM:
        telegram_bot.record_event(envelope)

    return JSONResponse(
        status_code=200,
        content={"status": "sent", "correlation_id": envelope.correlation_id},
    )


@app.post("/webhooks/retell/simulate")
async def retell_simulate(request: Request):
    if not settings.ENABLE_RETELL_SIMULATION:
        raise HTTPException(status_code=404, detail="Not Found")

    raw_body = await request.body()
    try:
        data = json.loads(raw_body)
    except Exception:
        return _error_response(400, "invalid_json")

    envelope = None
    if isinstance(data, dict) and data.get("version") == "v1":
        envelope = _parse_envelope(data)
        if not envelope:
            return _error_response(400, "invalid_envelope")
    else:
        idempotency_key = hashlib.sha256(raw_body).hexdigest()
        envelope = EventEnvelope(
            version="v1",
            source="retell",
            type="call_simulated",
            idempotency_key=idempotency_key,
            timestamp=int(time.time()),
            correlation_id=str(uuid.uuid4()),
            payload=data,
        )

    result = await bus.publish(envelope)
    if result.status == "duplicate":
        return JSONResponse(
            status_code=200,
            content={"status": "duplicate", "correlation_id": result.correlation_id},
        )

    if settings.ENABLE_TELEGRAM:
        telegram_bot.record_event(envelope)

    return JSONResponse(
        status_code=200,
        content={"status": "accepted", "correlation_id": result.correlation_id},
    )


# --- TEST ENDPOINTS ---


@app.post("/integrations/test/telegram")
async def test_telegram():
    correlation_id = str(uuid.uuid4())
    await bus.publish(
        "ticket.created",
        {
            "guest_name": "Test Bot",
            "room_number": "000",
            "issue": "Connectivity Test",
        },
        correlation_id,
    )
    return {"status": "triggered", "correlation_id": correlation_id}


@app.post("/integrations/test/make")
async def test_make():
    correlation_id = str(uuid.uuid4())
    await handle_make_trigger({"type": "test_ping"}, correlation_id)
    return {"status": "triggered", "correlation_id": correlation_id}


# --- DASHBOARD API ---


@app.get("/staff/recent-tickets")
def get_recent_tickets():
    db = SessionLocal()
    try:
        tickets = (
            db.query(Escalation).order_by(Escalation.created_at.desc()).limit(20).all()
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
    correlation_id = str(uuid.uuid4())
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

        await bus.publish(
            "ticket.created",
            {
                "guest_name": new_ticket.guest_name,
                "room_number": new_ticket.room_number,
                "issue": new_ticket.issue,
            },
            correlation_id,
        )

        return {"status": "Ticket Created", "correlation_id": correlation_id}
    finally:
        db.close()


@app.delete("/staff/tickets/{ticket_id}")
def delete_ticket(ticket_id: int):
    db = SessionLocal()
    try:
        ticket = db.query(Escalation).filter(Escalation.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        db.delete(ticket)
        db.commit()
        return {"status": "deleted", "id": ticket_id}
    finally:
        db.close()


# --- WEBHOOK ---
@app.post("/webhook")
async def handle_webhook(
    request: Request,
):
    if not settings.RETELL_SIGNING_SECRET:
        return _error_response(503, "retell_signing_secret_missing")

    raw_body = await request.body()
    timestamp = request.headers.get("X-Signature-Timestamp")
    signature = request.headers.get("X-Signature")

    try:
        verify_hmac_signature(
            raw_body=raw_body,
            timestamp=timestamp,
            signature=signature,
            secret=settings.RETELL_SIGNING_SECRET,
            tolerance_seconds=settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS,
        )
    except (SignatureMissingError, SignatureExpiredError, SignatureInvalidError):
        return _error_response(401, "unauthorized")

    try:
        payload = json.loads(raw_body)
    except Exception:
        return _error_response(400, "invalid_json")

    envelope = EventEnvelope(
        version="v1",
        source="retell",
        type=_derive_retell_type(payload),
        idempotency_key=hashlib.sha256(raw_body).hexdigest(),
        timestamp=int(time.time()),
        correlation_id=str(uuid.uuid4()),
        payload=payload,
    )

    result = await bus.publish(envelope)
    if result.status == "duplicate":
        return JSONResponse(
            status_code=200,
            content={
                "received": True,
                "status": "duplicate",
                "correlation_id": result.correlation_id,
            },
        )

    logger.info(
        "Webhook received",
        extra={"correlation_id": envelope.correlation_id},
    )
    return JSONResponse(
        status_code=200,
        content={
            "received": True,
            "status": "accepted",
            "correlation_id": envelope.correlation_id,
        },
    )


# --- VOICE BRAIN (WEBSOCKET) ---
@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info("AI Connected", extra={"correlation_id": call_id})

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
                logger.info("User transcript received", extra={"correlation_id": call_id})

                ai_reply = "I've noted that request."
                if settings.GOOGLE_API_KEY:
                    try:
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        response = model.generate_content(
                            "You are a hotel concierge named Grace. "
                            f"User says: {user_text}. Keep it short."
                        )
                        ai_reply = response.text
                    except Exception as exc:
                        logger.warning(
                            "AI generation failed: %s",
                            exc,
                            extra={"correlation_id": call_id},
                        )

                if len(user_text) > 5:
                    db = SessionLocal()
                    try:
                        new_ticket = Escalation(
                            guest_name="Voice Call Guest",
                            room_number="Unknown",
                            issue=user_text,
                            status="OPEN",
                            sentiment="Neutral",
                        )
                        db.add(new_ticket)
                        db.commit()
                        logger.info("Real-time Ticket Saved", extra={"correlation_id": call_id})

                        event_id = str(uuid.uuid4())
                        await bus.publish(
                            "ticket.created",
                            {
                                "guest_name": new_ticket.guest_name,
                                "room_number": new_ticket.room_number,
                                "issue": new_ticket.issue,
                                "call_id": call_id,
                            },
                            event_id,
                        )
                    finally:
                        db.close()

                response_event = {
                    "response_type": "response",
                    "response_id": data["response_id"],
                    "content": ai_reply,
                    "content_complete": True,
                    "end_call": False,
                }
                await websocket.send_json(response_event)

    except Exception as exc:
        logger.warning("Connection Closed: %s", exc, extra={"correlation_id": call_id})
