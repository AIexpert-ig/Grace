import os
import json
from typing import Any
import uuid
import logging
import hashlib
import hmac
import time
from datetime import datetime

import httpx
from fastapi import FastAPI, WebSocket, Request, HTTPException
from starlette.websockets import WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings
from app.core.events import EventEnvelope, bus, logger
from app.core.security import (
    SignatureExpiredError,
    SignatureInvalidError,
    SignatureMissingError,
    verify_hmac_signature,
)
from app.services import telegram_bot
from app.services.make_integration import handle_make_trigger, send_make_webhook

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

engine = create_engine(settings.DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

BUILD_SHA = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GITHUB_SHA") or "unknown"
BUILD_MARK = "grace-build-2026-02-09"

@app.get("/__build")
def __build():
    return {
        "sha": BUILD_SHA,
        "service": "Grace",
        "routes": {
            "deadletter": bool(settings.ADMIN_TOKEN),
            "make_ingress": bool(settings.ENABLE_MAKE_WEBHOOKS),
            "retell_diagnose": bool(_diagnostics_enabled()),
            "telegram_webhook": bool(settings.ENABLE_TELEGRAM),
        },
        "mark": BUILD_MARK,
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

api_key = settings.google_api_key
if api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
    except Exception as exc:
        logger.debug("Google GenerativeAI import/config failed: %s", exc)

@app.on_event("startup")
async def startup():
    if settings.ENABLE_TELEGRAM:
        bus.subscribe("ticket.created", telegram_bot.handle_ticket_created)
    if settings.ENABLE_MAKE_WEBHOOKS:
        bus.subscribe("ticket.created", handle_make_trigger)
    logger.info("Grace AI Event Bus Online")


def _error_response(status_code: int, error: str, correlation_id: str | None = None) -> JSONResponse:
    payload = {"error": error}
    if correlation_id:
        payload["correlation_id"] = correlation_id
    return JSONResponse(status_code=status_code, content=payload)


def _auth_error(required_header: str, reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": "unauthorized",
            "required_header": required_header,
            "reason": reason,
        },
    )


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


def _require_admin_token(request: Request) -> JSONResponse | None:
    if not settings.ADMIN_TOKEN:
        return _error_response(503, "admin_token_missing")
    if request.headers.get("X-Admin-Token") != settings.ADMIN_TOKEN:
        return _error_response(401, "unauthorized")
    return None


def _diagnostics_enabled() -> bool:
    return settings.ENV != "production" or settings.ENABLE_DIAGNOSTIC_ENDPOINTS


def _is_valid_telegram_update(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        return False
    for key in ("message", "edited_message", "channel_post", "callback_query"):
        if key in payload:
            return True
    return False

@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Grace Hotel AI"}

@app.get("/events/deadletter")
def get_deadletters(request: Request):
    admin_error = _require_admin_token(request)
    if admin_error:
        return admin_error
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

    raw_body = await request.body()
    admin_header = request.headers.get("X-Admin-Token")
    admin_ok = False

    if settings.ADMIN_TOKEN and admin_header:
        if hmac.compare_digest(admin_header, settings.ADMIN_TOKEN):
            admin_ok = True
        else:
            return _auth_error("X-Admin-Token", "invalid_admin_token")

    if not admin_ok:
        if settings.MAKE_SIGNING_SECRET:
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
                return _auth_error("X-Signature", "missing_signature_headers")
            except SignatureExpiredError:
                return _auth_error("X-Signature", "timestamp_invalid_or_expired")
            except SignatureInvalidError:
                return _auth_error("X-Signature", "signature_mismatch")
        else:
            return _auth_error("X-Admin-Token", "missing_admin_token")

    if not settings.MAKE_WEBHOOK_URL:
        return _error_response(503, "make_webhook_url_missing")

    try:
        payload = json.loads(raw_body)
    except Exception:
        return _error_response(400, "invalid_envelope")

    envelope = _parse_envelope(payload)
    if not envelope:
        return _error_response(400, "invalid_envelope")

    try:
        await send_make_webhook(settings.MAKE_WEBHOOK_URL, envelope)
    except Exception:
        return _error_response(502, "make_webhook_failed", correlation_id=envelope.correlation_id)

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

@app.get("/integrations/test/telegram")
@app.post("/integrations/test/telegram")
async def test_telegram(request: Request):
    admin_error = _require_admin_token(request)
    if admin_error:
        return admin_error
    cid = str(uuid.uuid4())
    await bus.publish("ticket.created", {
        "guest_name": "Test Bot",
        "room_number": "000",
        "issue": "Connectivity Test"
    }, cid)
    return {"status": "triggered", "correlation_id": cid}

@app.get("/integrations/test/make")
@app.post("/integrations/test/make")
async def test_make(request: Request):
    admin_error = _require_admin_token(request)
    if admin_error:
        return admin_error
    cid = str(uuid.uuid4())
    await handle_make_trigger({"type": "test_ping"}, cid)
    return {"status": "triggered", "correlation_id": cid}

# --- DASHBOARD API ---

@app.get("/staff/recent-tickets")
def get_recent_tickets():
    db = SessionLocal()
    try:
        tickets = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(20).all()
        return [
            {
                "id": t.id,
                "guest_name": t.guest_name,
                "room_number": t.room_number,
                "issue": t.issue,
                "status": t.status,
                "sentiment": t.sentiment,
                "created_at": t.created_at.isoformat()
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
            "sentiment_score": 98
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
            sentiment=data.get("sentiment", "Neutral")
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

# Voice Hook
@app.post("/webhook")
async def handle_webhook(request: Request):
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
    except SignatureMissingError:
        return _error_response(401, "missing_signature_headers")
    except SignatureExpiredError:
        return _error_response(401, "timestamp_invalid_or_expired")
    except SignatureInvalidError as exc:
        if exc.message == "Invalid timestamp":
            return _error_response(401, "timestamp_invalid_or_expired")
        return _error_response(401, "signature_mismatch")

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

@app.post("/webhooks/retell/diagnose")
async def retell_diagnose(request: Request):
    if not _diagnostics_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    admin_error = _require_admin_token(request)
    if admin_error:
        return admin_error

    if not settings.RETELL_SIGNING_SECRET:
        return _error_response(503, "retell_signing_secret_missing")

    try:
        data = await request.json()
    except Exception:
        return _error_response(400, "invalid_json")

    timestamp = data.get("timestamp")
    raw_body = data.get("raw_body")
    provided_signature = data.get("signature")
    if timestamp is None or raw_body is None or provided_signature is None:
        return _error_response(400, "invalid_request")
    if not isinstance(raw_body, str):
        return _error_response(400, "invalid_request")

    try:
        timestamp_int = int(timestamp)
        timestamp_within_tolerance = (
            abs(int(time.time()) - timestamp_int)
            <= settings.WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
        )
    except (TypeError, ValueError):
        timestamp_within_tolerance = False

    timestamp_str = str(timestamp)
    signed_string = f"{timestamp_str}.{raw_body}"
    computed_signature = hmac.new(
        settings.RETELL_SIGNING_SECRET.encode(),
        signed_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    provided = str(provided_signature).strip()
    if provided.lower().startswith("sha256="):
        provided = provided.split("=", 1)[1]
    provided = provided.lower()

    signature_matches = hmac.compare_digest(computed_signature, provided)

    return JSONResponse(
        status_code=200,
        content={
            "canonical_string_preview": signed_string[:64],
            "expected_signature_hex_prefix": computed_signature[:8],
            "received_signature_prefix": provided[:8],
            "match": signature_matches,
            "timestamp_within_tolerance": timestamp_within_tolerance,
            "encoding": "hex (sha256= prefix allowed)",
        },
    )

# Telegram Inbound Webhook
@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info("telegram_webhook_received", extra={"payload": data})

        message = data.get("message")
        if not isinstance(message, dict):
            return {"ok": True}

        user_text = message.get("text")
        if not isinstance(user_text, str):
            return {"ok": True}

        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        if user_text.strip().startswith("/start"):
            reply_text = "Hello! I'm Grace, your hotel concierge. How can I help you today?"
        else:
            reply_text = "Thanks for your message. I have received it and will get back to you shortly."

        token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
        if not token:
            logger.error("telegram_webhook_failed: missing_bot_token")
            return {"ok": False}
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"chat_id": chat_id, "text": reply_text},
            )
            response.raise_for_status()

        return {"ok": True}
    except Exception as exc:
        logger.error("telegram_webhook_failed: %s", exc)
        return {"ok": False}

SYSTEM_PROMPT = (
    "You are the AI concierge for Courtyard by Marriott Al Barsha in Dubai.\n"
    "Be concise, polite, and helpful.\n"
    "If the guest greeting is unclear, ask how you may assist.\n"
    "Never acknowledge a request unless one exists.\n"
    "Do not repeat yourself."
)

_RETELL_STATE: dict[str, dict[str, Any]] = {}

def _retell_state(call_id: str) -> dict[str, Any]:
    state = _RETELL_STATE.get(call_id)
    if not state:
        state = {"last_assistant": []}
        _RETELL_STATE[call_id] = state
    return state

def _last_user_text(data: dict) -> str:
    transcript = data.get("transcript")
    if isinstance(transcript, list):
        for item in reversed(transcript):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return ""

def _is_unclear(text: str) -> bool:
    if not text or not text.strip():
        return True
    lowered = text.strip().lower()
    return lowered in {"hello", "hello?", "hi", "hi?", "hey", "hey?"}

def _clarify() -> str:
    return "Good afternoon, how may I assist you today?"

def _loop_break() -> str:
    return "Good afternoon, how may I assist you today?"

# Voice WebSocket
async def _retell_ws_handler(websocket: WebSocket, call_id: str | None = None) -> None:
    await websocket.accept()
    logger = logging.getLogger("retell")
    path = websocket.scope.get("path")
    logger.info("RETELL_WS_ACCEPT call_id=%s path=%s", call_id, path)
    response_counter = 0

    try:
        await websocket.send_json(
            {
                "response_id": 0,
                "content": "",
                "content_complete": True,
                "end_call": False,
            }
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect as e:
                code = getattr(e, "code", None)
                reason = getattr(e, "reason", None)
                if code == 1000:
                    logger.info("RETELL_WS_CLOSED_NORMAL call_id=%s code=%s reason=%s", call_id, code, reason)
                else:
                    logger.warning("RETELL_WS_CLOSED call_id=%s code=%s reason=%s", call_id, code, reason)
                return
            interaction_type = data.get("interaction_type")
            call_id = data.get("call_id") or data.get("conversation_id") or call_id
            response_id_in = data.get("response_id")
            user_text = _last_user_text(data)
            preview = (user_text[:40] + "…") if len(user_text) > 40 else user_text
            logger.info(
                "RETELL_WS_RECV call_id=%s interaction_type=%s response_id=%s preview=%s",
                call_id,
                interaction_type,
                response_id_in,
                preview,
            )

            if interaction_type == "update_only":
                continue
            if interaction_type != "response_required":
                continue

            if _is_unclear(user_text):
                ai_reply = _clarify()
            else:
                ai_reply = ""
                if settings.google_api_key:
                    try:
                        import google.generativeai as genai
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        response = model.generate_content(
                            [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": user_text},
                            ]
                        )
                        ai_reply = (response.text or "").strip()
                    except Exception:
                        ai_reply = ""

                if not ai_reply:
                    ai_reply = "I'm experiencing a technical issue. How may I assist you today?"

                state = _retell_state(call_id or "unknown")
                last_assistant = state["last_assistant"]
                if any(ai_reply.strip() == prev for prev in last_assistant[-2:]):
                    ai_reply = _loop_break()
                last_assistant.append(ai_reply.strip())
                if len(last_assistant) > 3:
                    del last_assistant[:-3]

            try:
                resp_id_int = int(response_id_in)
                response_counter = max(response_counter, resp_id_int)
                response_id = resp_id_int
            except Exception:
                response_counter += 1
                response_id = response_counter

            logger.info(
                "RETELL_WS_SEND call_id=%s response_id=%s preview=%s",
                call_id,
                response_id,
                (ai_reply[:40] + "…") if len(ai_reply) > 40 else ai_reply,
            )

            if len(user_text) > 5:
                db = SessionLocal()
                try:
                    t = Escalation(
                        guest_name="Voice Guest",
                        room_number="Unknown",
                        issue=user_text,
                        status="OPEN",
                        sentiment="Neutral",
                    )
                    db.add(t)
                    db.commit()
                    await bus.publish("ticket.created", {"guest_name": "Voice Guest", "issue": user_text}, call_id)
                finally:
                    db.close()

            await websocket.send_json(
                {
                    "response_id": response_id,
                    "content": ai_reply,
                    "content_complete": True,
                    "end_call": False,
                }
            )
    except Exception:
        logger.exception("RETELL_WS_ERROR_UNEXPECTED call_id=%s", call_id)
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/llm-websocket")
async def websocket_endpoint_root(websocket: WebSocket):
    await _retell_ws_handler(websocket)


@app.websocket("/llm-websocket/{call_id}")
async def websocket_endpoint_with_id(websocket: WebSocket, call_id: str):
    await _retell_ws_handler(websocket, call_id)
